from functions import *
# df_population=df_population, df_shops=df_shops, df_cafe=df_cafe, df_orgs=df_orgs, df_trans=df_trans

def math_features(df_population=pd.DataFrame(), df_shops=pd.DataFrame(), df_cafe=pd.DataFrame(), df_orgs=pd.DataFrame(), df_trans=pd.DataFrame()):
    population = round(df_population['count_people'].sum() / 15)

    shop_distances = count_distance(df_population, df_shops)
    cafe_distances = count_distance(df_population, df_cafe)
    bank_distances = count_distance(df_population, df_orgs[df_orgs['type'] == 'bank'])
    atm_distances = count_distance(df_population, df_orgs[df_orgs['type'] == 'atm'])
    station_distances = count_distance(df_population, df_trans)

    shop_mean_distance = np.array(shop_distances).mean()
    cafe_mean_distance = np.array(cafe_distances).mean()
    bank_mean_distance = np.array(bank_distances).mean()
    atm_mean_distance = np.array(atm_distances).mean()
    station_mean_distance = np.array(station_distances).mean()

    # transport_flow

    df = pd.DataFrame({'population': population, 'shop_distances': [shop_distances], 'cafe_distances': [cafe_distances],
                       'bank_distances': [bank_distances], 'atm_distances': [atm_distances], 'station_distances': [station_distances],
                        'shop_mean_distance': shop_mean_distance, 'cafe_mean_distance': cafe_mean_distance,
                       'bank_mean_distance': bank_mean_distance, 'atm_mean_distance': atm_mean_distance, 'station_mean_distance': station_mean_distance})

    df.to_csv('address_features.csv', sep=';')