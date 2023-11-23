import geopandas as gpd
import warnings
import pandas as pd
import numpy as np
import json
import h3
import folium
import osmnx as ox
from math import cos, sin, pi, sqrt
from geopy.distance import geodesic
from shapely import wkt
from folium.plugins import HeatMap
from shapely.geometry import Polygon, Point, MultiPolygon
import shapely.wkt
from time import sleep
from tqdm import tqdm
import csv

# массив для работы функции find_shop
shops = [['Соседи', 'Соседи экспресс', 'Соседи Экспресс', 'Соседи 7-2'], ['Евроопт'], ['Семейный']]

def join_str(str):
    result = ''
    for s in str:
         result += ' ' + s
    return result[1:]

# сбор информации с OSM в населенном пункте по тегу и формирование фрагмента DataFrame
def osm_query(tag, city, search_tags):
    gdf = ox.geometries_from_place(city, tag).reset_index()
    gdf['city'] = np.full(len(gdf), city.split(',')[0])
    gdf['object'] = np.full(len(gdf), list(tag.keys())[0])
    gdf['type'] = np.full(len(gdf), tag[list(tag.keys())[0]])
    gdf_cols = set(gdf.columns) & set(search_tags)
    gdf = gdf[gdf_cols]
    return gdf

# поиск по массивам городов и тегов, формирование конечного DataFrame
def get_data(tags, cities, search_tags):
    gdfs = []    
    for city in cities:
        sleep(0.25)
        for tag in tags:
            gdf = osm_query(tag, city, search_tags)
            gdfs.append(gdf)
            
            if 'geometry' in gdf.columns:
                lat, lon = get_lat_lon(gdf['geometry'])
                gdf['lat'] = lat
                gdf['lon'] = lon

            else:
                gdf['geometry'] = np.NaN
                gdf['lat'] = np.NaN
                gdf['lon'] = np.NaN
            
    data_poi = pd.concat(gdfs)
    return data_poi

# поиск в DataFrame магазинов самой организации для выделения исключительно конкурентов
def find_shop(df, name):
    select_shop = pd.Series()
    for i in range(len(shops)):
        if name in shops[i]:
            select_shop = df.loc[df['name:ru'].isin(shops[i])]
        
            if select_shop.empty:
                select_shop = df.loc[df['name'].isin(shops[i])]

            if select_shop.empty:
                select_shop = df.loc[df['name:en'].isin(shops[i])]
    
    return select_shop

# подсчет плотности населения
def population_density(data_poi):
    data_poi['building:levels'] = data_poi['building:levels'].fillna(1)
    data_poi = data_poi.rename(columns = {'building:levels' : 'levels'})

    apartments = ['apartments' , 'dormitory']
    houses = ['house', 'semidetached_house', 'detached', 'terrace']
    people_ctn = []

    for i in range(len(data_poi)):

        if data_poi['type'].iloc[i] in apartments:

            people = data_poi['levels'][i]*data_poi['geometry'][i].area

        elif data_poi['type'].iloc[i] in houses:

            people = data_poi['levels'][i]*data_poi['geometry'][i].area

        else:
            people = 'not living area'

        people_ctn.append(people)

    data_poi['square'] = people_ctn

    table_people = data_poi.query("square != 'not living area'")
    return table_people

# карта плотности населения
def create_heatmap(data, lat_lon_feature, m):
    HeatMap(data[lat_lon_feature].groupby(lat_lon_feature[0:2]).sum().reset_index().values.tolist(),
            radius=70, min_opacity=0.05, max_val=int((data[lat_lon_feature[2]]).quantile([0.75])), blur=30).add_to(m)
    return m

# отрисовка полигона по координатам
def visualize_polygons(geometry):
    lats, lons = get_lat_lon(geometry)
    
    m = folium.Map(location=[sum(lats)/len(lats), sum(lons)/len(lons)], zoom_start=13, tiles='cartodbpositron')
    overlay = gpd.GeoSeries(geometry).to_json()
    folium.GeoJson(overlay, name = 'boundary').add_to(m)
    
    return m

# выделение координат из геометрии OSM
def get_lat_lon(geometry):  
    lon = geometry.apply(lambda x: x.x if x.type == 'Point' else x.centroid.x)
    lat = geometry.apply(lambda x: x.y if x.type == 'Point' else x.centroid.y)
    return lat, lon

# получение центров гексов в координатах
def centers_of_hex(geoJson):
    hexagons = list(h3.polyfill(geoJson, 9))
    polygons_centres = []
    for hex in hexagons:
        centres = list(h3.h3_to_geo(hex))
        polygons_centres.append(centres)
    
    return polygons_centres

# формирование окружения гекса
def union_of_six(hexagon, polygons_centres):
    union = [hexagon]
    for i in range(len(polygons_centres)):
        if 310 < geodesic((hexagon[0], hexagon[1]), (polygons_centres[i][0],polygons_centres[i][1])). m < 360:
            union.append(polygons_centres[i])
    
    return union

# множество с массивами окружений
def union_set(coors):
    union_set = []
    for i in range(len(coors)):
        union_set.append(union_of_six(coors[i], coors))
        
    return union_set

# массив хэш-адресов по центрам
def hexes_by_centers(coors):
    h3_address = []
    for i in range(len(coors)):
         from_coors = h3.geo_to_h3(coors[i][0], coors[i][1],  9)
         h3_address.append(from_coors)
        
    return h3_address

# покрытие гексагонами
def create_hexagons(geoJson):
    
    polyline = geoJson['coordinates'][0]

    polyline.append(polyline[0])
    lat = [p[0] for p in polyline]
    lng = [p[1] for p in polyline]
    m = folium.Map(location=[sum(lat)/len(lat), sum(lng)/len(lng)], zoom_start=13, tiles='cartodbpositron')
    my_PolyLine=folium.PolyLine(locations=polyline,weight=3,color="purple")
    m.add_child(my_PolyLine)

    hexagons = list(h3.polyfill(geoJson, 9))
    
    polylines = []
    lat = []
    lng = []
    for hex in hexagons:
        polygons = h3.h3_set_to_multi_polygon([hex], geo_json=False)
        outlines = [loop for polygon in polygons for loop in polygon]
        polyline = [outline + [outline[0]] for outline in outlines][0]
        lat.extend(map(lambda v:v[0],polyline))
        lng.extend(map(lambda v:v[1],polyline))
        polylines.append(polyline)
    for polyline in polylines:
        my_PolyLine=folium.PolyLine(locations=polyline,weight=3,color='purple')
        m.add_child(my_PolyLine)
        
    polylines_x = []
    for j in range(len(polylines)):
        a = np.column_stack((np.array(polylines[j])[:,1],np.array(polylines[j])[:,0])).tolist()
        polylines_x.append([(a[i][0], a[i][1]) for i in range(len(a))])
        
    polygons_hex = pd.Series(polylines_x).apply(lambda x: Polygon(x))
        
    return m, polygons_hex, polylines

# отрисовка гексагона
def visualize_hexagons(hexagons, color="purple", folium_map=None, one_hex=False):

    polylines = []
    lat = []
    lng = []
    for hex in hexagons:
        polygons = h3.h3_set_to_multi_polygon([hex], geo_json=False)
        outlines = [loop for polygon in polygons for loop in polygon]
        polyline = [outline + [outline[0]] for outline in outlines][0]
        lat.extend(map(lambda v:v[0],polyline))
        lng.extend(map(lambda v:v[1],polyline))
        polylines.append(polyline)
    
    if folium_map is None:
        m = folium.Map(location=[sum(lat)/len(lat), sum(lng)/len(lng)], zoom_start=14, tiles='cartodbpositron')
    else:
        m = folium_map

    if one_hex == True:
        for polyline in polylines:
            my_PolyLine=folium.PolyLine(locations=polyline,weight=3,color=color, opacity=0.6)
        return my_PolyLine

    else:
        for polyline in polylines:
            my_PolyLine=folium.PolyLine(locations=polyline,weight=3,color=color, opacity=0.6)
            m.add_child(my_PolyLine)
        return m

# функция отделения геометрии населенного пункта от LineString
def transform_to_only_polygons(polygon_krd):
    indexes = []
    all_indexes = []
    for i in polygon_krd['geometry'].index:
        all_indexes.append(i)

    for i in polygon_krd['geometry'].index:
        if polygon_krd['geometry'][i].geom_type == 'Polygon' or polygon_krd['geometry'][i].geom_type == 'MultiPolygon':
            indexes.append(i)

    drop_indexes = set(all_indexes)^set(indexes)
    polygon_krd = polygon_krd[~polygon_krd.index.isin(drop_indexes)]
    return polygon_krd

# перевод геодезической системы координат в прямоугольную
def transform_coors(data_poi):
    for i in range(len(data_poi['geometry'])):
        data_poi['geometry'][i] = shapely.wkt.loads(data_poi['geometry'][i])
        
    for j in range(len(data_poi['geometry'])):
        coords = []
        if data_poi['geometry'][j].geom_type == 'Polygon':
            for i in range(len(data_poi['geometry'][j].exterior.coords)):
                L = data_poi['geometry'][j].exterior.coords[i][0]
                B = data_poi['geometry'][j].exterior.coords[i][1]
                N = pow(6378100, 2)/(sqrt(pow(6378100, 2)*cos(B*pi/180)*cos(B*pi/180) + pow(6356800, 2)*sin(B*pi/180)*sin(B*pi/180)))

                x = abs((N+160)*cos(B*pi/180)*cos(L*pi/180))
                y = abs((N+160)*cos(B*pi/180)*sin(L*pi/180))

                coords.append((x, y))
            data_poi['geometry'][j] = Polygon(coords)
        elif data_poi['geometry'][j].geom_type == 'Point':
            L = data_poi['geometry'][j].coords[0][0]
            B = data_poi['geometry'][j].coords[0][1]
            N = pow(6378100, 2)/(sqrt(pow(6378100, 2)*cos(B*pi/180)*cos(B*pi/180) + pow(6356800, 2)*sin(B*pi/180)*sin(B*pi/180)))

            x = abs((N+160)*cos(B*pi/180)*cos(L*pi/180))
            y = abs((N+160)*cos(B*pi/180)*sin(L*pi/180))
            
            data_poi['geometry'][j] = Point(x,y)
        else:
            polygons = []
            for polygon in data_poi['geometry'][j]:
                for i in range(len(polygon.exterior.coords)):
                    L = polygon.exterior.coords[i][0]
                    B = polygon.exterior.coords[i][1]
                    N = pow(6378100, 2)/(sqrt(pow(6378100, 2)*cos(B*pi/180)*cos(B*pi/180) + pow(6356800, 2)*sin(B*pi/180)*sin(B*pi/180)))

                    x = abs((N+160)*cos(B*pi/180)*cos(L*pi/180))
                    y = abs((N+160)*cos(B*pi/180)*sin(L*pi/180))

                    coords.append((x, y))
                polygon = Polygon(coords)
                polygons.append(polygon)
            data_poi['geometry'][j] = MultiPolygon(polygons)
    return data_poi

# принадлженость точки множеству точек, ограниченному фигурой
def in_polygon(x, y, xp, yp):
    c=0
    for i in range(len(xp)):
        if (((yp[i]<=y and y<yp[i-1]) or (yp[i-1]<=y and y<yp[i])) and 
            (x > (xp[i-1] - xp[i]) * (y - yp[i]) / (yp[i-1] - yp[i]) + xp[i])): c = 1 - c    
    return bool(c)

# определение, в каком гексагоне лежит координата
def which_polygon(x, y, coors):
    result = []
    h3_address = set(hexes_by_centers(coors)) # массив хэш-адресов гексагонов
    h3_address = list(h3_address)
    for i in range(len(h3_address)):
        hexagon = h3.h3_to_geo_boundary(h3_address[i])
        xp = []
        yp = []

        for items in hexagon:
            xp.append(items[0])

        for items in hexagon:
            yp.append(items[1])

        if in_polygon(x, y, xp, yp):
            result.append(h3_address[i])
            
        if result != []:
            return result
    
    return result

# подсчет расстояний до объектов
def count_distance(address, object):
    distances = []

    for i in object.index:
        distances.append(geodesic((address['lat'][address.index[0]], address['lon'][address.index[0]]), (object['lat'][i], object['lon'][i])).m)

    return distances