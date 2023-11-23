from flask import Flask, Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (jsonify, request)
import plotly.express as px
import dash
import dash_html_components as html
import plotly.io
from autocorrector import autocorrector
from functions import *
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, current_user, logout_user





app = Flask(__name__)

app.config['SECRET_KEY'] = 'secret-key-goes-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'

db = SQLAlchemy(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))

# db.create_all(app=app)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/signup', methods=['POST'])
def signup_post():
    with app.app_context():
        db.create_all()
    email = request.form.get('email')
    name = request.form.get('name')
    password = request.form.get('password')

    user = User.query.filter_by(email=email).first()  # if this returns a user, then the email already exists in database

    if user:  # if a user is found, we want to redirect back to signup page so user can try again
        flash('Данный e-mail уже существует')
        return redirect(url_for('signup'))


    # create a new user with the form data. Hash the password so the plaintext version isn't saved.
    new_user = User(email=email, name=name, password=generate_password_hash(password, method='pbkdf2:sha256'))

    # add the new user to the database
    db.session.add(new_user)
    db.session.commit()
    return redirect(url_for('login'))

@app.route('/login', methods=['POST'])
def login_post():
    with app.app_context():
        db.create_all()
    email = request.form.get('email')
    password = request.form.get('password')
    remember = True if request.form.get('remember') else False

    user = User.query.filter_by(email=email).first()

    # check if the user actually exists
    # take the user-supplied password, hash it, and compare it to the hashed password in the database
    if not user or not check_password_hash(user.password, password):
        flash('Неверный e-mail или пароль.')
        return redirect(url_for('login')) # if the user doesn't exist or password is wrong, reload the page

    login_user(user, remember=remember)
    return redirect(url_for('profile'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', name=current_user.name)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

df_all = pd.read_csv('data/all_data.csv', sep=';')
df_all = df_all.astype({'addr:street':'str'})

df = pd.DataFrame()
df_shop = pd.DataFrame()
df_orgs = pd.DataFrame()
df_trans = pd.DataFrame()
df_cafe = pd.DataFrame()
app1 = dash.Dash('my_first_app')

app1.layout = html.Div([])

dashboard = app1.layout

count_orgs = 0
count_shop = 0
count_people = 0
count_cafe = 0
count_trans = 0
traffic = 0


def generate_html(dataframe: pd.DataFrame):
    # get the table HTML from the dataframe
    table_html = dataframe.to_html(table_id="table")
    # construct the complete HTML with jQuery Data tables
    # You can disable paging or enable y scrolling on lines 20 and 21 respectively
    html = f"""
    <html>
    <header>
        <link href="https://cdn.datatables.net/1.11.5/css/jquery.dataTables.min.css" rel="stylesheet">
    </header>
    <body>
    {table_html}
    <script src="https://code.jquery.com/jquery-3.6.0.slim.min.js" integrity="sha256-u7e5khyithlIdTpu22PHhENmPcRdFiHRjhAuHcs05RI=" crossorigin="anonymous"></script>
    <script type="text/javascript" src="https://cdn.datatables.net/1.11.5/js/jquery.dataTables.min.js"></script>
    <script>
        $(document).ready( function () {{
            $('#table').DataTable({{
                // paging: false,    
                // scrollY: 400,
            }});
        }});
    </script>
    </body>
    </html>
    """
    # return the html
    return html

def visualize_hexagons_rate(hexagons, folium_map=None):
    polylines = []
    lat = []
    lng = []
    for hex in hexagons:
        polygons = h3.h3_set_to_multi_polygon([hex], geo_json=False)
        outlines = [loop for polygon in polygons for loop in polygon]
        polyline = [outline + [outline[0]] for outline in outlines][0]
        lat.extend(map(lambda v: v[0], polyline))
        lng.extend(map(lambda v: v[1], polyline))
        polylines.append(polyline)

    if folium_map is None:
        m = folium.Map(location=[sum(lat) / len(lat), sum(lng) / len(lng)], zoom_start=14, tiles='cartodbpositron')
    else:
        m = folium_map

    for polyline in polylines:
        if polyline == polylines[0]:
            my_PolyLine = folium.PolyLine(locations=polyline, weight=3, color='green')
            m.add_child(my_PolyLine)
        elif polyline == polylines[1]:
            my_PolyLine = folium.PolyLine(locations=polyline, weight=3, color='yellow')
            m.add_child(my_PolyLine)
        elif polyline == polylines[2]:
            my_PolyLine = folium.PolyLine(locations=polyline, weight=3, color='red')
            m.add_child(my_PolyLine)
        else:
            my_PolyLine = folium.PolyLine(locations=polyline, weight=3, color='grey')
            m.add_child(my_PolyLine)
    return m

def find_info(city, street, house, union=False, hexes=False):
    data = pd.read_csv('data/new_data.csv', sep=';')
    df = data
    df = df[df['city'] == city]
    df = df.replace(np.nan, '-', regex=True)
    df = df[df['addr:street'].str.contains(f'{street}')]
    df = df[df['addr:housenumber'] == house]

    if not df.empty:
        hexagon = df['hexagon'][df.index[0]]

    else:
        df = pd.read_csv('data/all_adr.csv', sep=';')
        df = df[df['city'] == city]
        df = df.replace(np.nan, '-', regex=True)
        df = df[df['addr:street'].str.contains(f'{street}')]
        df = df[df['addr:housenumber'] == house]
        hexagon = df['hex'][df.index[0]]


    df_population = data[data['object'] == 'building']
    df_population = df_population[df_population['type'] == 'apartments']


    df_trans = data[data['object'].isin(['railway', 'public_transport', 'amenity'])]
    df_trans = df_trans[df_trans['type'].isin(['station', 'halt', 'platform', 'stop_position', 'parking', 'tram_stop', 'subway_entrance'])]

    df_shop = data[data['object'].isin(['shop', 'landuse', 'amenity'])]
    df_shop = df_shop[df_shop['type'].isin(['convenience', 'supermarket', 'bakery', 'butcher', 'variety_store', 'alcohol',
                                            'greengrocer', 'department_store', 'confectionery', 'mall', 'beverages', 'tobacco',
                                            'farm', 'seafood', 'pastry', 'dairy', 'retail', 'marketplace', 'deli', 'vacant', 'wholesale'])]



    df_orgs = data[data['object'].isin(['amenity', 'building', 'office'])]
    df_orgs = df_orgs[df_orgs['type'].isin(['place_of_worship', 'school', 'bank', 'kindergarten', 'hospital',
                                            'atm', 'post_office', 'clinic', 'doctors', 'townhall', 'police',
                                            'social_facility', 'dentist', 'college', 'university', 'courthouse',
                                            'bureau_de_change', 'music_school', 'training', 'chapel', 'mosque', 'dormitory',
                                            'government', 'cathedral', 'educational_institution', 'monastery', 'language_school',
                                            'temple', 'prep_school', 'administrative'])]


    df_cafe = data[data['object'].isin(['amenity', 'shop'])]
    df_cafe = df_cafe[df_cafe['type'].isin(['restaurant', 'cafe', 'fast_food', 'pub', 'bar', 'coffee'])]


    if union == True:

        hexes = df['neighbours'][df.index[0]]
        hexes = hexes.replace("'", '')
        hexes = hexes[1:-1].split(', ')

        m = visualize_hexagons(hexes[1:], color='pink')
        visualize_hexagons([hexes[0]], one_hex=True).add_to(m)
        m.save('templates/hex.html')
        hex_data = pd.read_csv('data/new_data.csv', sep=';')
        hex_data = hex_data[hex_data['city'] == city]
        create_heatmap(hex_data, ['lat', 'lon', 'count_people'], m).save('templates/hex_heat.html')


        df_population = df_population[df_population['hexagon'].isin(hexes)]
        df_shop = df_shop[df_shop['hexagon'].isin(hexes)]
        df_orgs = df_orgs[df_orgs['hexagon'].isin(hexes)]
        df_trans = df_trans[df_trans['hexagon'].isin(hexes)]
        df_cafe = df_cafe[df_cafe['hexagon'].isin(hexes)]

        df_population = df_population[['city', 'type', 'addr:street', 'addr:housenumber', 'count_people']]
        df_shop = df_shop[['city', 'type', 'addr:street', 'addr:housenumber', 'name']]
        df_cafe = df_cafe[['city', 'type', 'addr:street', 'addr:housenumber', 'name']]
        df_orgs = df_orgs[['city', 'type', 'addr:street', 'addr:housenumber', 'name']]
        df_trans = df_trans[['city', 'type', 'addr:street', 'addr:housenumber', 'transport']]

        df_population = df_population.rename(
            columns={'city': 'город', 'type': 'тип объекта', 'addr:street': 'улица', 'addr:housenumber': 'дом',
                     'count_people': 'жилая площадь'})
        df_shop = df_shop.rename(
            columns={'city': 'город', 'type': 'тип объекта', 'addr:street': 'улица', 'addr:housenumber': 'дом',
                     'name': 'название'})
        df_cafe = df_cafe.rename(
            columns={'city': 'город', 'type': 'тип объекта', 'addr:street': 'улица', 'addr:housenumber': 'дом',
                     'name': 'название'})
        df_orgs = df_orgs.rename(
            columns={'city': 'город', 'type': 'тип объекта', 'addr:street': 'улица', 'addr:housenumber': 'дом',
                     'name': 'название'})
        df_trans = df_trans.rename(
            columns={'city': 'город', 'type': 'тип объекта', 'addr:street': 'улица', 'addr:housenumber': 'дом',
                     'transport': 'количество маршрутов'})

        df_shop = df_shop.replace(np.nan, '-', regex=True)
        df_cafe = df_cafe.replace(np.nan, '-', regex=True)
        df_orgs = df_orgs.replace(np.nan, '-', regex=True)
        df_trans = df_trans.replace(np.nan, '-', regex=True)

        return df_population, df_shop, df_orgs, df_trans, df_cafe


    else:

        df_population = df_population[df_population['hexagon'] == hexagon]
        df_shop = df_shop[df_shop['hexagon'] == hexagon]
        df_orgs = df_orgs[df_orgs['hexagon'] == hexagon]
        df_trans = df_trans[df_trans['hexagon'] == hexagon]
        df_cafe = df_cafe[df_cafe['hexagon'] == hexagon]


        df_population = df_population[['city', 'type', 'addr:street', 'addr:housenumber', 'count_people']]
        df_shop = df_shop[['city', 'type', 'addr:street', 'addr:housenumber', 'name']]
        df_cafe = df_cafe[['city', 'type', 'addr:street', 'addr:housenumber', 'name']]
        df_orgs = df_orgs[['city', 'type', 'addr:street', 'addr:housenumber', 'name']]
        df_trans = df_trans[['city', 'type', 'addr:street', 'addr:housenumber', 'transport']]



        df_population = df_population.rename(columns={'city': 'город', 'type': 'тип объекта', 'addr:street': 'улица', 'addr:housenumber': 'дом',
                                'count_people': 'жилая площадь'})
        df_shop = df_shop.rename(columns={'city': 'город', 'type': 'тип объекта', 'addr:street': 'улица', 'addr:housenumber': 'дом',
                                'name': 'название'})
        df_cafe = df_cafe.rename(columns={'city': 'город', 'type': 'тип объекта', 'addr:street': 'улица', 'addr:housenumber': 'дом',
                                'name': 'название'})
        df_orgs = df_orgs.rename(columns={'city': 'город', 'type': 'тип объекта', 'addr:street': 'улица', 'addr:housenumber': 'дом',
                     'name': 'название'})
        df_trans = df_trans.rename(columns={'city': 'город', 'type': 'тип объекта', 'addr:street': 'улица', 'addr:housenumber': 'дом',
                     'transport': 'количество маршрутов'})

        df_shop = df_shop.replace(np.nan, '-', regex=True)
        df_cafe = df_cafe.replace(np.nan, '-', regex=True)
        df_orgs = df_orgs.replace(np.nan, '-', regex=True)
        df_trans = df_trans.replace(np.nan, '-', regex=True)

        if not hexes:
            make_map([hexagon])
            hex_data = pd.read_csv('data/new_data.csv', sep=';')
            hex_data = hex_data[hex_data['city'] == city]
            create_heatmap(hex_data, ['lat', 'lon', 'count_people'], visualize_hexagons([hexagon])).save('templates/hex_heat.html')

            return df_population, df_shop, df_orgs, df_trans, df_cafe
        if hexes:
            return df_population, df_shop, df_orgs, df_trans, df_cafe, hexagon

def count_info(data_n, data_sh_n, data_org_n, data_tran_n, df_cafe):

    population_n = round(data_n['жилая площадь'].sum() / 15)
    shops_n = len(data_sh_n)
    orgs_n = len(data_org_n)
    trans_n = len(data_tran_n)
    traff = data_tran_n['количество маршрутов'].sum()
    cafe = len(df_cafe)

    return population_n, shops_n, orgs_n, trans_n, traff, cafe

def make_map(hexagon):
    new_map = visualize_hexagons(hexagon)
    new_map.save('templates/hex.html')

def make_map_rate(hexagon):
    new_map = visualize_hexagons_rate(hexagon)
    new_map.save('templates/hex.html')

def make_map_filter(hexagon):
    new_map = visualize_hexagons_rate(hexagon)
    new_map.save('templates/hex.html')

def find_by_filters(city, min, max, checkboxes):
    numbers = []
    mall_tags = ['mall', 'retail']
    supermarket_tags = ['department_store', 'supermarket', 'variety_store']
    product_tags = ['convenience', 'butcher', 'alcohol', 'beverages', 'tobacco', 'seafood', 'vacant']
    farm_tags = ['farm', 'deli', 'dairy', 'butcher']
    market_tags = ['marketplace']
    fruit_tags = ['greengrocer']
    candy_tags = ['bakery', 'confectionery', 'pastry']
    opt_tags = ['wholesale']

    if min['population'] == '':
        min['population'] = 0

    if min['cafe'] == '':
        min['cafe'] = 0

    if min['shops'] == '':
        min['shops'] = 0

    if min['organizations'] == '':
        min['organizations'] = 0

    if min['transport'] == '':
        min['transport'] = 0

    if max['population'] == '':
        max['population'] = 1000000000

    if max['cafe'] == '':
        max['cafe'] = 1000000000

    if max['shops'] == '':
        max['shops'] = 1000000000

    if max['organizations'] == '':
        max['organizations'] = 1000000000

    if max['transport'] == '':
        max['transport'] = 1000000000


    data = pd.read_csv('data/new_hexes_all.csv', sep=';')
    data.pop('Unnamed: 0.1')
    data = data[data['city'] == city]
    data = data[data['population'] >= float(min['population'])]
    data = data[data['population'] <= float(max['population'])]

    print(len(list(data.index)))

    data = data[data['cafe'] >= int(min['cafe'])]
    data = data[data['cafe'] <= int(max['cafe'])]
    print(len(list(data.index)))

    for i in list(data.index):
        if int(min['shops']) <= int(data['shops'][i][2]) <= int(max['shops']):
            numbers.append(i)
    data = data.loc[numbers]
    numbers = []
    print(len(list(data.index)))

    for i in list(data.index):
        if int(min['organizations']) <= int(data['organizations'][i][2]) <= int(max['organizations']):
            numbers.append(i)
    data = data.loc[numbers]
    numbers = []
    print(len(list(data.index)))

    for i in list(data.index):
        if int(min['transport']) <= int(data['transport'][i][2]) <= int(max['transport']):
            numbers.append(i)
    data = data.loc[numbers]
    numbers = []
    print(len(list(data.index)))

    data = data.replace(mall_tags, 'торговый центр', regex=True)
    if checkboxes['mall'] == 'on':
        for i in list(data.index):
            if 'торговый центр' in data['shops'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace(supermarket_tags, 'супермаркет', regex=True)
    if checkboxes['supermarket'] == 'on':
        for i in list(data.index):
            if 'супермаркет' in data['shops'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace(product_tags, 'продуктовый магазин', regex=True)
    if checkboxes['product'] == 'on':
        for i in list(data.index):
            if 'продуктовый магазин' in data['shops'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace(farm_tags, 'фермерский магазин', regex=True)
    if checkboxes['farm'] == 'on':
        for i in list(data.index):
            if 'фермерский магазин' in data['shops'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace(market_tags, 'рынок', regex=True)
    if checkboxes['market'] == 'on':
        for i in list(data.index):
            if 'рынок' in data['shops'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace(fruit_tags, 'фруктово-овощная лавка', regex=True)
    if checkboxes['fruit'] == 'on':
        for i in list(data.index):
            if 'фруктово-овощная лавка' in data['shops'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace(candy_tags, 'пекарня/кондитерская', regex=True)
    if checkboxes['candy'] == 'on':
        for i in list(data.index):
            if 'пекарня/кондитерская' in data['shops'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace(opt_tags, 'оптовый магазин', regex=True)
    if checkboxes['opt'] == 'on':
        for i in list(data.index):
            if 'оптовый магазин' in data['shops'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    numbers = []


    school_tags = ['school', 'music_school', 'language_school', 'prep_school']
    universe_tags = ['college', 'university', 'training', 'dormitory']
    kinder_tags = ['kindergarten']
    church_tags = ['place_of_worship', 'monastery', 'chapel', 'mosque', 'temple', 'cathedral']
    bank_tags = ['bank', 'atm', 'bureau_de_change']
    med_tags = ['hospital', 'clinic', 'doctors', 'dentist']
    post_tags = ['post_office']
    gos_tags = ['townhall', 'police', 'social_facility', 'courthouse', 'government']

    data = data.replace(school_tags, 'школа', regex=True)
    if checkboxes['school'] == 'on':
        for i in list(data.index):
            if 'школа' in data['organizations'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace(universe_tags, 'университет/колледж', regex=True)
    if checkboxes['universe'] == 'on':
        for i in list(data.index):
            if 'университет/колледж' in data['organizations'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace(kinder_tags, 'детский сад', regex=True)
    if checkboxes['kinder'] == 'on':
        for i in list(data.index):
            if 'детский сад' in data['organizations'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace(church_tags, 'религиозное учреждение', regex=True)
    if checkboxes['church'] == 'on':
        for i in list(data.index):
            if 'религиозное учреждение' in data['organizations'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace(bank_tags, 'банк/банкомат', regex=True)
    if checkboxes['bank'] == 'on':
        for i in list(data.index):
            if 'банк/банкомат' in data['organizations'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace(med_tags, 'медицинское учреждение', regex=True)
    if checkboxes['med'] == 'on':
        for i in list(data.index):
            if 'медицинское учреждение' in data['organizations'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace(post_tags, 'почта', regex=True)
    if checkboxes['post'] == 'on':
        for i in list(data.index):
            if 'почта' in data['organizations'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace(gos_tags, 'государственное учреждение', regex=True)
    if checkboxes['gos'] == 'on':
        for i in list(data.index):
            if 'государственное учреждение' in data['organizations'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]
    numbers = []

    data = data.replace('subway_entrance', 'вход в метро', regex=True)
    if checkboxes['metro'] == 'on':
        for i in list(data.index):
            if 'вход в метро' in data['transport'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    data = data.replace('parking', 'парковка', regex=True)
    if checkboxes['parking'] == 'on':
        for i in list(data.index):
            if 'парковка' in data['transport'][i]:
                numbers.append(i)
        numbers = list(set(numbers))
        data = data.loc[numbers]

    bus_tags = ['tram_stop', 'platform', 'stop_position', 'station']
    data = data.replace(bus_tags, 'остановка', regex=True)
    bus_tags = ['остановка']
    if checkboxes['bus'] == 'on':
        for i in list(data.index):
            for tag in bus_tags:
                if tag in data['transport'][i]:
                    numbers.append(i)

        numbers = list(set(numbers))
        data = data.loc[numbers]

    train_tags = ['station', 'halt']
    data = data.replace(train_tags, 'станция', regex=True)
    train_tags = ['станция']
    if checkboxes['train'] == 'on':
        for i in list(data.index):
            for tag in train_tags:
                if tag in data['transport'][i]:
                    numbers.append(i)
        data = data.loc[numbers]

    data = data[data['hex'] != '0']
    data.pop('Unnamed: 0')

    data = data.rename(columns={'hex':'код гексагона', 'population':'плотность населения', 'shops':'магазины', 'cafe':'пункты питания', 'organizations':'организации', 'transport':'транспорт', 'traffic':'автобусные маршруты', 'city':'город'})


    return data

def translate_type(df, df_shop, df_cafe, df_orgs, df_trans):
    df = df.replace('apartments', 'жилое здание', regex=True)

    mall_tags = ['mall', 'retail']
    supermarket_tags = ['department_store', 'supermarket', 'variety_store']
    product_tags = ['convenience', 'butcher', 'alcohol', 'beverages', 'tobacco', 'seafood']
    farm_tags = ['farm', 'deli', 'dairy', 'butcher']
    market_tags = ['marketplace']
    fruit_tags = ['greengrocer']
    candy_tags = ['bakery', 'confectionery', 'pastry']
    opt_tags = ['wholesale']
    df_shop = df_shop.replace(mall_tags, 'торговый центр', regex=True)
    df_shop = df_shop.replace(supermarket_tags, 'супермаркет', regex=True)
    df_shop = df_shop.replace(product_tags, 'продуктовый магазин', regex=True)
    df_shop = df_shop.replace(farm_tags, 'фермерский магазин', regex=True)
    df_shop = df_shop.replace(market_tags, 'рынок', regex=True)
    df_shop = df_shop.replace(fruit_tags, 'фруктово-овощная лавка', regex=True)
    df_shop = df_shop.replace(candy_tags, 'кондитерская/пекарня', regex=True)
    df_shop = df_shop.replace(opt_tags, 'оптовый магазин', regex=True)

    school_tags = ['school', 'music_school', 'language_school', 'prep_school']
    universe_tags = ['college', 'university', 'training', 'dormitory']
    kinder_tags = ['kindergarten']
    church_tags = ['place_of_worship', 'monastery', 'chapel', 'mosque', 'temple', 'cathedral']
    bank_tags = ['bank', 'atm', 'bureau_de_change']
    med_tags = ['hospital', 'clinic', 'doctors', 'dentist']
    post_tags = ['post_office']
    gos_tags = ['townhall', 'police', 'social_facility', 'courthouse', 'government']

    df_orgs = df_orgs.replace(school_tags, 'школа', regex=True)
    df_orgs = df_orgs.replace(universe_tags, 'колледж/университет', regex=True)
    df_orgs = df_orgs.replace(kinder_tags, 'детский сад', regex=True)
    df_orgs = df_orgs.replace(church_tags, 'религиозное учреждение', regex=True)
    df_orgs = df_orgs.replace(med_tags, 'медицинское учреждение', regex=True)
    df_orgs = df_orgs.replace(bank_tags, 'банк/банкомат', regex=True)
    df_orgs = df_orgs.replace(post_tags, 'почта', regex=True)
    df_orgs = df_orgs.replace(gos_tags, 'государственное учреждение', regex=True)

    bus_tags = ['tram_stop', 'platform', 'stop_position', 'station', 'station', 'halt']
    df_trans = df_trans.replace('subway_entrance', 'метро', regex=True)
    df_trans = df_trans.replace('parking', 'парковка', regex=True)
    df_trans = df_trans.replace('subway_entrance', 'метро', regex=True)
    df_trans = df_trans.replace(bus_tags, 'остановка/станция', regex=True)

    df_cafe = df_cafe.replace('restaurant', 'ресторан', regex=True)
    df_cafe = df_cafe.replace('cafe', 'кафе', regex=True)
    df_cafe = df_cafe.replace('fast_food', 'ресторан быстрого питания', regex=True)
    df_cafe = df_cafe.replace(['pub', 'bar'], 'бар', regex=True)
    df_cafe = df_cafe.replace('coffee', 'кофейня', regex=True)

    return df, df_shop, df_cafe, df_orgs, df_trans


@app.route('/')
@app.route('/home')
def main():
    return render_template("main.html")

@app.route('/home_admin')
@login_required
def main_admin():
    return render_template("main_admin.html")

@app.route('/address', methods =["GET", "POST"])
@login_required
def gfg(df=df, df_shop=df_shop, df_orgs=df_orgs, df_trans=df_trans, df_cafe=df_cafe, count_people=count_people, count_shop=count_shop, count_orgs=count_orgs, count_trans=count_trans, traffic=traffic, count_cafe=count_cafe):

    if request.method == "POST":
        address = request.form.get("address")
        city = request.form.get("state")

        if city == '':
            city = "Минск"

        if address == '':
            address = "проспект Независимости, 39"

        street = address.split(' ')[:-1]
        street = join_str(street)
        house = address.split(' ')[-1]

        street = join_str(autocorrector(df_all, city, street))

        if request.form.get("union") == 'on':
            df, df_shop, df_orgs, df_trans, df_cafe = find_info(city, street, house, union=True)
            count_people, count_shop, count_orgs, count_trans, traffic, count_cafe = count_info(df, df_shop, df_orgs, df_trans, df_cafe)

        else:
            df, df_shop, df_orgs, df_trans, df_cafe = find_info(city, street, house)
            count_people, count_shop, count_orgs, count_trans, traffic, count_cafe = count_info(df, df_shop, df_orgs, df_trans, df_cafe)

        df, df_shop, df_cafe, df_orgs, df_trans = translate_type(df, df_shop, df_cafe, df_orgs, df_trans)
        return render_template("base.html", df=df, df_shop=df_shop, df_orgs=df_orgs, df_trans=df_trans, df_cafe=df_cafe, count_people=count_people, count_shop=count_shop, count_orgs=count_orgs, count_trans=count_trans, traffic=traffic, count_cafe=count_cafe)

    df, df_shop, df_cafe, df_orgs, df_trans = translate_type(df, df_shop, df_cafe, df_orgs, df_trans)
    return render_template("base.html", df=df, df_shop=df_shop, df_orgs=df_orgs, df_trans=df_trans, df_cafe=df_cafe, count_people=count_people, count_shop=count_shop, count_orgs=count_orgs, count_trans=count_trans, traffic=traffic, count_cafe=count_cafe)

@app.route('/hex')
@login_required
def hex():
    return render_template("hex.html")

@app.route('/contacts', methods =["GET", "POST"])
def contacts():
    if request.method == 'POST':
        name = "Имя: " + str(request.form.get('fn')) + '\n'
        email = "Почта: " + str(request.form.get('email')) + '\n'
        mess = "Сообщение: " + str(request.form.get('message'))

        message = name + email + mess

        addr_from = "geoanalytics.retail@gmail.com"  # Адресат
        addr_to = ["lukomskie.com@gmail.com", "yakovlevmaxim.ds@gmail.com", "alexadim2015@gmail.com", "AlexeiKarnauhov@gmail.com"]  # Получатель
        password = "oxipvbrujttkkljb"  # Пароль, его надо сгенерить, заходишь вот сюда и по инструкции:

        msg = MIMEMultipart()  # Создаем сообщение

        msg['From'] = addr_from  # Адресат
        msg['To'] = ", ".join(addr_to)  # Получатель
        msg['Subject'] = 'Ответ с сайта'  # Тема сообщения

        msg.attach(MIMEText(message, 'plain'))  # Добавляем в сообщение текст

        server = smtplib.SMTP('smtp.gmail.com', 587)  # Создаем объект SMTP, забил параметры именно для gmail почты
        server.set_debuglevel(True)  # Включаем режим отладки - если отчет не нужен, строку можно закомментировать
        server.starttls()  # Начинаем шифрованный обмен по TLS
        server.login(addr_from, password)  # Получаем доступ
        server.send_message(msg)  # Отправляем сообщение
        server.quit()

    return render_template("contacts.html")

@app.route('/contacts_admin', methods =["GET", "POST"])
def contacts_admin():
    if request.method == 'POST':
        name = "Имя: " + str(request.form.get('fn')) + '\n'
        email = "Почта: " + str(request.form.get('email')) + '\n'
        mess = "Сообщение: " + str(request.form.get('message'))

        message = name + email + mess

        addr_from = "geoanalytics.retail@gmail.com"  # Адресат
        addr_to = ["lukomskie.com@gmail.com", "yakovlevmaxim.ds@gmail.com", "alexadim2015@gmail.com", "AlexeiKarnauhov@gmail.com"]  # Получатель
        password = "oxipvbrujttkkljb"  # Пароль, его надо сгенерить, заходишь вот сюда и по инструкции:

        msg = MIMEMultipart()  # Создаем сообщение

        msg['From'] = addr_from  # Адресат
        msg['To'] = ", ".join(addr_to)  # Получатель
        msg['Subject'] = 'Ответ с сайта'  # Тема сообщения

        msg.attach(MIMEText(message, 'plain'))  # Добавляем в сообщение текст

        server = smtplib.SMTP('smtp.gmail.com', 587)  # Создаем объект SMTP, забил параметры именно для gmail почты
        server.set_debuglevel(True)  # Включаем режим отладки - если отчет не нужен, строку можно закомментировать
        server.starttls()  # Начинаем шифрованный обмен по TLS
        server.login(addr_from, password)  # Получаем доступ
        server.send_message(msg)  # Отправляем сообщение
        server.quit()

    return render_template("contacts_admin.html")

@app.route('/hex_heat')
@login_required
def hex_heat():
    return render_template("hex_heat.html")

@app.route('/difference', methods =["GET", "POST"])
@login_required
def diff(df=df, df_shop=df_shop, df_orgs=df_orgs, df_trans=df_trans, df_cafe=df_cafe, count_people=count_people, count_shop=count_shop, count_orgs=count_orgs, count_trans=count_trans, traffic=traffic, count_cafe=count_cafe, dashboard=dashboard):
    address_1 = '-'
    address_2 = '-'
    address_3 = '-'
    if request.method == "POST":
        hexagons = []

        address_1 = request.form.get("address_1")
        city_1 = request.form.get("state_1")

        if city_1 == '':
            city_1 = "Минск"

        if address_1 == '':
            address_1 = "проспект Независимости, 39"

        street_1 = address_1.split(' ')[:-1]
        street_1 = join_str(street_1)
        house_1 = address_1.split(' ')[-1]

        street_1 = join_str(autocorrector(df_all, city_1, street_1))


        df_1, df_shop_1, df_orgs_1, df_trans_1, df_cafe_1, hexagon_1 = find_info(city_1, street_1, house_1, hexes=True)
        hexagons.append(hexagon_1)
        count_people_1, count_shop_1, count_orgs_1, count_trans_1, traffic_1, count_cafe_1 = count_info(df_1, df_shop_1, df_orgs_1, df_trans_1, df_cafe_1)

        address_2 = request.form.get("address_2")
        city_2 = request.form.get("state_2")

        if city_2 == '':
            city_2 = "Минск"

        if address_2 == '':
            address_2 = "проспект Независимости, 42"

        street_2 = address_2.split(' ')[:-1]
        street_2 = join_str(street_2)
        house_2 = address_2.split(' ')[-1]


        street_2 = join_str(autocorrector(df_all, city_2, street_2))


        df_2, df_shop_2, df_orgs_2, df_trans_2, df_cafe_2, hexagon_2 = find_info(city_2, street_2, house_2, hexes=True)
        hexagons.append(hexagon_2)
        count_people_2, count_shop_2, count_orgs_2, count_trans_2, traffic_2, count_cafe_2 = count_info(df_2, df_shop_2,
                                                                                                        df_orgs_2,
                                                                                                        df_trans_2,
                                                                                                        df_cafe_2)

        address_3 = request.form.get("address_3")
        city_3 = request.form.get("state_3")

        if city_3 == '':
            city_3 = "Минск"

        if address_3 == '':
            address_3 = "Киселева, 4"

        street_3 = address_3.split(' ')[:-1]
        street_3 = join_str(street_3)
        house_3 = address_3.split(' ')[-1]

        street_3 = join_str(autocorrector(df_all, city_3, street_3))

        df_3, df_shop_3, df_orgs_3, df_trans_3, df_cafe_3, hexagon_3 = find_info(city_3, street_3, house_3, hexes=True)
        hexagons.append(hexagon_3)
        count_people_3, count_shop_3, count_orgs_3, count_trans_3, traffic_3, count_cafe_3 = count_info(df_3, df_shop_3,
                                                                                                        df_orgs_3,
                                                                                                        df_trans_3,
                                                                                                        df_cafe_3)

        dashboard = []
        fig = []

        diagram_people = pd.DataFrame()
        diagram_people['адрес'] = pd.Series([address_1, address_2, address_3])
        diagram_people['плотность населения'] = pd.Series([count_people_1, count_people_2, count_people_3])
        fig.append(px.bar(diagram_people, x="адрес", y="плотность населения"))

        diagram_shops = pd.DataFrame()
        diagram_shops['адрес'] = pd.Series([address_1, address_2, address_3])
        diagram_shops['магазины'] = pd.Series([count_shop_1, count_shop_2, count_shop_3])
        fig.append(px.bar(diagram_shops, x="адрес", y="магазины"))

        diagram_cafe = pd.DataFrame()
        diagram_cafe['адрес'] = pd.Series([address_1, address_2, address_3])
        diagram_cafe['точки питания'] = pd.Series([count_cafe_1, count_cafe_2, count_cafe_3])
        fig.append(px.bar(diagram_cafe, x="адрес", y="точки питания"))

        diagram_orgs = pd.DataFrame()
        diagram_orgs['адрес'] = pd.Series([address_1, address_2, address_3])
        diagram_orgs['организации'] = pd.Series([count_orgs_1, count_orgs_2, count_orgs_3])
        fig.append(px.bar(diagram_orgs, x="адрес", y="организации"))

        diagram_trans = pd.DataFrame()
        diagram_trans['адрес'] = pd.Series([address_1, address_2, address_3])
        diagram_trans['остановки'] = pd.Series([count_trans_1, count_trans_2, count_trans_3])
        fig.append(px.bar(diagram_trans, x="адрес", y="остановки"))

        diagram_traf = pd.DataFrame()
        diagram_traf['адрес'] = pd.Series([address_1, address_2, address_3])
        diagram_traf['маршруты'] = pd.Series([traffic_1, traffic_2, traffic_3])
        fig.append(px.bar(diagram_traf, x="адрес", y="маршруты"))

        for i in range(len(fig)):
            dashboard.append(plotly.io.to_html(fig[i]))

            dashboard[i] = dashboard[i].replace('<html>', '')
            dashboard[i] = dashboard[i].replace('<head>', '')
            dashboard[i] = dashboard[i].replace('<meta charset="utf-8" /></head>', '')
            dashboard[i] = dashboard[i].replace('<body>', '')
            dashboard[i] = dashboard[i].replace('</html>', '')
            dashboard[i] = dashboard[i].replace('</body>', '')


        make_map_rate(hexagons)
        hex_data = pd.read_csv('data/new_data.csv', sep=';')
        hex_data = hex_data[hex_data['city'].isin([city_1, city_2, city_3])]
        create_heatmap(hex_data, ['lat', 'lon', 'count_people'], visualize_hexagons_rate(hexagons)).save(
            'templates/hex_heat.html')

        df_1, df_shop_1, df_cafe_1, df_orgs_1, df_trans_1 = translate_type(df_1, df_shop_1, df_cafe_1, df_orgs_1,
                                                                           df_trans_1)
        df_2, df_shop_2, df_cafe_2, df_orgs_2, df_trans_2 = translate_type(df_2, df_shop_2, df_cafe_2, df_orgs_2,
                                                                           df_trans_2)
        df_3, df_shop_3, df_cafe_3, df_orgs_3, df_trans_3 = translate_type(df_3, df_shop_3, df_cafe_3, df_orgs_3,
                                                                           df_trans_3)
        return render_template("difference.html", address_1=address_1, address_2=address_2, address_3=address_3, df=[df_1, df_2, df_3], df_shop=[df_shop_1, df_shop_2, df_shop_3], df_orgs=[df_orgs_1, df_orgs_2, df_orgs_3],
                               df_trans=[df_trans_1, df_trans_2, df_trans_3], df_cafe=[df_cafe_1, df_cafe_2, df_cafe_3], count_people=[count_people_1, count_people_2, count_people_3],
                               count_shop=[count_shop_1, count_shop_2, count_shop_3], count_orgs=[count_orgs_1, count_orgs_2, count_orgs_3],
                               count_trans=[count_trans_1, count_trans_2, count_trans_3], traffic=[traffic_1, traffic_2, traffic_3], count_cafe=[count_cafe_1, count_cafe_2, count_cafe_3], dashboard=dashboard)


    return render_template("difference.html", address_1=address_1, address_2=address_2, address_3=address_3, df=[df, df, df], df_shop=[df_shop, df_shop, df_shop], df_orgs=[df_orgs, df_orgs, df_orgs], df_trans=[df_trans, df_trans, df_trans], df_cafe=[df_cafe, df_cafe, df_cafe], count_people=[0,0,0], count_shop=[0,0,0], count_orgs=[0,0,0], count_trans=[0,0,0], traffic=[0,0,0], count_cafe=[0,0,0], dashboard=dashboard)

@app.route('/checkboxes', methods =["GET", "POST"])
@login_required
def check(df=df, df_shop=df_shop, df_orgs=df_orgs, df_trans=df_trans, df_cafe=df_cafe, count_people=count_people, count_shop=count_shop, count_orgs=count_orgs, count_trans=count_trans, traffic=traffic, count_cafe=count_cafe):
    if request.method == "POST":
        city = request.form.get("state")

        pop_min = request.form.get("pop_min")
        pop_max = request.form.get("pop_max")

        cafe_min = request.form.get("cafe_min")
        cafe_max = request.form.get("cafe_max")

        shop_min = request.form.get("shop_min")
        shop_max = request.form.get("shop_max")

        orgs_min = request.form.get("orgs_min")
        orgs_max = request.form.get("orgs_max")

        trans_min = request.form.get("trans_min")
        trans_max = request.form.get("trans_max")

        checkboxes = {'mall': request.form.get("sh_mall"), 'supermarket': request.form.get("sh_sup"), 'product': request.form.get("sh_pr"),
                      'farm': request.form.get("sh_farm"), 'market': request.form.get("sh_mark"), 'fruit': request.form.get("sh_fr"),
                      'candy': request.form.get("sh_bake"), 'opt': request.form.get("sh_opt"),
                      'school': request.form.get("or_sch"), 'universe': request.form.get("or_un"),
                      'kinder': request.form.get("or_kind"), 'church': request.form.get("or_rel"),
                      'bank': request.form.get("or_bank"), 'med': request.form.get("or_med"),
                      'post': request.form.get("or_post"), 'gos': request.form.get("or_gos"),
                      'metro': request.form.get("tr_metro"), 'bus': request.form.get("tr_bus"),
                      'train': request.form.get("tr_zd"), 'parking': request.form.get("tr_park")}

        df = find_by_filters(city, min={'population': pop_min, 'cafe': cafe_min, 'shops':shop_min, 'organizations': orgs_min, 'transport':
                                   trans_min}, max={'population': pop_max, 'cafe': cafe_max, 'shops':shop_max, 'organizations': orgs_max, 'transport':
                                   trans_max}, checkboxes=checkboxes)
        count = len(df)

        if not df.empty:
            make_map(df['код гексагона'].array)
            hex_data = pd.read_csv('data/new_data.csv', sep=';')
            hex_data = hex_data[hex_data['city'] == city]
            create_heatmap(hex_data, ['lat', 'lon', 'count_people'], visualize_hexagons_rate(df['код гексагона'].array)).save(
                'templates/hex_heat.html')

        return render_template("checkboxes.html", df=df, count=count, df_orgs=df_orgs, df_trans=df_trans, df_cafe=df_cafe, count_people=count_people, count_shop=count_shop, count_orgs=count_orgs, count_trans=count_trans, traffic=traffic, count_cafe=count_cafe)


    return render_template("checkboxes.html", df=df, df_shop=df_shop, df_orgs=df_orgs, df_trans=df_trans, df_cafe=df_cafe, count_people=count_people, count_shop=count_shop, count_orgs=count_orgs, count_trans=count_trans, traffic=traffic, count_cafe=count_cafe)


if __name__== "__main__":
    app.run(debug=True)