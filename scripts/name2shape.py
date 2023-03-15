# Created by: Anderson Brito
# Email: andersonfbrito@gmail.com
# Release date: 29-12-2021
# Last update: 2023-03-15

from geopy.geocoders import Nominatim
from shapely.geometry import Point
from difflib import SequenceMatcher
import pandas as pd
import geopandas as gpd
import numpy as np
import argparse
import os
import os.path

# from shapely.errors import ShapelyDeprecationWarning
# import warnings; warnings.filterwarnings('ignore', "", ShapelyDeprecationWarning)

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

pd.set_option('display.max_columns', 500)
import platform
print('Python version:', platform.python_version())
print('Pandas version:', pd.__version__)
print('Geopandas version:', gpd.__version__)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Match location names to shapefile polygons, using coordinates",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--input", required=True, help="TVS file containing location names")
    parser.add_argument("--shapefile", required=True, help="Shapefile with polygons to be matched with location names")
    parser.add_argument("--display", required=False, default='no', choices=['no', 'yes'], help="Display header of the shapefile for inspection, and exit?")
    parser.add_argument("--fix-projection", required=False, default='no', choices=['no', 'yes'], help="Fix map projection of second shape file base on the first one provided?")
    parser.add_argument("--geo-columns", required=False, help="List of columns with distinct levels of geographic names to be searched")
    parser.add_argument("--add-geo", required=False, help="Extra column to be added with standard value applicable to all entries, e.g. 'country:Brazil'")
    parser.add_argument("--lat", required=False, default='lat', help="Column containing latitude data, if already existing in input file")
    parser.add_argument("--long", required=False, default='long', help="Column containing latitude data, if already existing in input file")
    parser.add_argument("--cache", required=False, help="TSV file with cached coordinates")
    parser.add_argument("--save-latlong", required=False, default='yes', choices=['no', 'yes'], help="Export coordinate columns 'lat' and 'long'?")
    parser.add_argument("--check-match", required=False, help="Column in shapefile containing the names of locations to be matched")
    parser.add_argument("--target", required=False, help="Comma-separated list of shapefile columns to be exported in the final output")
    parser.add_argument("--same-format", required=False, default='yes', choices=['no', 'yes'], help="Should all columns and rows in the input file be exported?")
    parser.add_argument("--output", required=False, help="Name of the TSV output file")
    args = parser.parse_args()

    input = args.input
    shapefile = args.shapefile
    display_header = args.display
    fix_projection = args.fix_projection
    geo_cols = args.geo_columns
    add_geo_cols = args.add_geo
    output_coordinates = args.save_latlong
    lat_col = args.lat
    long_col = args.long
    cache = args.cache
    check_col = args.check_match
    target_cols = args.target
    same_file = args.same_format
    output = args.output

    # path = '/Users/anderson/google_drive/ITpS/projetos_itps/resp_pathogens/analyses/20220314_relatorio3/'
    # os.chdir(path)
    # input = path + 'combined_testdata2_short.tsv'
    # shapefile = "/Users/anderson/google_drive/codes/geoCodes/bra_adm_ibge_2020_shp/bra_admbnda_adm2_ibge_2020.shp"
    # display_header = 'no'
    # fix_projection = 'no'
    # geo_cols = "state, location"
    # add_geo_cols = 'country:Brazil'
    # output_coordinates = 'no'
    # lat_col = 'lat'
    # long_col = 'long'
    # cache = path + 'config/cache_coordinates.tsv'
    # check_col = 'ADM2_PT'
    # target_cols = "ADM1_PT, ADM1_PCODE, ADM2_PT, ADM2_PCODE"
    # same_file = 'yes'
    # output = path + "test.tsv"

    geolocator = Nominatim(user_agent="email@gmail.com")  # add your email here

    def load_table(file):
        df = ''
        if str(file).split('.')[-1] == 'tsv':
            separator = '\t'
            df = pd.read_csv(file, encoding='utf-8', sep=separator, dtype='str')
        elif str(file).split('.')[-1] == 'csv':
            separator = ','
            df = pd.read_csv(file, encoding='utf-8', sep=separator, dtype='str')
        elif str(file).split('.')[-1] in ['xls', 'xlsx']:
            df = pd.read_excel(file, index_col=None, header=0, sheet_name=0, dtype='str')
            df.fillna('', inplace=True)
        else:
            print('Wrong file format. Compatible file formats: TSV, CSV, XLS, XLSX')
            exit()
        return df

    threshold = 0.75

    # load geopandas
    geodf = gpd.read_file(shapefile)
    if display_header.lower() == 'yes':
        dict_df = geodf.head(1).to_dict('list')

        print('\nExample of column available in shapefile:')
        for col, val in dict_df.items():
            if col != 'geometry':
                print('\t- ' + col + ' = ' + str(val[0]))
            else:
                print('\t- ' + col + ' = POLYGON (...)')

        shapedata = geodf.drop(columns='geometry')
        shapedata.to_csv('shapedata.tsv', sep='\t', index=False)
        exit()


    # Load sample metadata
    df1 = load_table(input)
    df1.fillna('', inplace=True)

    # add columns with new geographic levels, applicable to all locations (e.g. country, state)
    new_cols = []
    if add_geo_cols not in ['', None]:
        new_cols = [c.strip() for c in add_geo_cols.split(',')]
        for col in new_cols:
            col_name, col_value = col.split(':')
            df1[col_name] = col_value

    geo_cols = [c.strip() for c in geo_cols.split(',')]
    geo_cols = [c.split(':')[0].strip() for c in new_cols] + geo_cols
    last_level = geo_cols[-1]

    # search coordinates (if any is missing)
    df2 = gpd.GeoDataFrame(columns = geo_cols + [lat_col, long_col] + ['geometry'])
    if lat_col not in df1.columns.tolist():
        lat_col = 'lat'
        long_col = 'long'
        df1[lat_col] = ''
        df1[long_col] = ''



    # cache coordinates
    df3 = pd.DataFrame()
    if cache not in ['', None]:
        if not os.path.isfile(cache):
            os.system("touch %s" % (cache))
        else:
            df3 = load_table(cache)
            df3.fillna('', inplace=True)
            place = [p for p in df3.columns.tolist() if p not in ['lat', 'long']]
            df3['place'] = df3[place].astype(str).agg(', '.join, axis=1)
            df3['coordinates'] = list(zip(df3['lat'], df3['long']))

    if not df3.empty:
        found = pd.Series(df3.coordinates.values, index=df3.place).to_dict()
    else:
        found = {}

    # find coordinates for locations not found in cache or XML file
    def find_coordinates(place):
        try:
            location = geolocator.geocode(place, language='en')
            lat, long = location.latitude, location.longitude
            coord = (str(lat), str(long))
            return coord
        except:
            coord = ('NA', 'NA')
            return coord

    notfound = []
    if '' in df1['lat'].tolist():
        print('\nSearching coordinates...')

    if 'state' in df1.columns.tolist():
        state_codes = {'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas', 'BA': 'Bahia', 'CE': 'Ceará', 'DF': 'Distrito Federal', 'ES': 'Espírito Santo', 'GO': 'Goiás', 'MA': 'Maranhão', 'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul', 'MG': 'Minas Gerais', 'PA': 'Pará', 'PB': 'Paraíba', 'PR': 'Paraná', 'PE': 'Pernambuco', 'PI': 'Piauí', 'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte', 'RS': 'Rio Grande do Sul', 'RO': 'Rondônia', 'RR': 'Roraima', 'SC': 'Santa Catarina', 'SP': 'São Paulo', 'SE': 'Sergipe', 'TO': 'Tocantins'}
        df1['state'] = df1['state'].apply(lambda x: state_codes[x] if x in state_codes else x)
    df1 = df1.sort_values(by=geo_cols)

    # print(df1['state'])

    printed = []
    for i, (name, df) in enumerate(df1.groupby(geo_cols)):
        # for id, row in df.iterrows():
        row_1 = df.iloc[0]

        if same_file == 'yes': # export results of coordinate shapefile search to same file used as input
            columns = df1.columns.tolist()
        else: # save in a separate, non-redundant file
            columns = geo_cols

        # query = [df.loc[idx, t] for t in geo_cols if t != 'region']
        query = [p for p in name]

        lat = row_1[lat_col]
        long = row_1[long_col]
        # print(lat, long)
        count = 0
        # if coordinatres already found, proceed
        if lat != '':
            lat, long = float(lat), float(long)
            coord = (lat, long)
            found[', '.join(query)] = coord  # record this coordinate as found
            df['lat'] = lat
            df['long'] = long
            df['geometry'] = Point(long, lat)
            df2 = df2.append(df, ignore_index=True)  # geodataframe used as output
#            print('\t- ' + ', '.join(list(name)) + ': ' + str(len(df.index)) + ' samples')
            # print(df)
        else: # if not found yet, search coordinates
            coord = ('NA', 'NA')
            if ', '.join(query) not in found: # then, search coordinates
                target = query[-1]
                if target not in ['', 'NA', 'NAN', 'unknown', '-', np.nan, None]:
                    coord = find_coordinates(', '.join(query)) # search coordinates
                    if 'NA' not in coord: # if search successful
                        # print('*   (' + coord[0] + ', ' + coord[1] + ') \t→ ' + ', '.join(query))
                        data = {'lat': coord[0], 'long': coord[1]}
                        for num, column in enumerate(geo_cols):
                            data[column] = query[num]
                        # print(data)
                        df3 = df3.append(data, ignore_index=True) # populate cache coordinates
            else: # if coordinate was found in previous steps
                coord = found[', '.join(query)]
                record = '    (' + coord[0] + ', ' + coord[1] + ') \t→ ' + ', '.join(query)
                if record not in printed:
                    # print(record)
                    printed.append(record)

            # if new coordinates were found, append data to output dataframe
            if 'NA' not in coord:
                # if already found, OR requested to output file in same format as the input file
                if ', '.join(query) not in found or same_file == 'yes':
                    # if same_file == 'yes' or '-'.join(query) not in found:
                    lat, long = float(coord[0]), float(coord[1])
                    df['lat'] = lat
                    df['long'] = long
                    df['geometry'] = Point(long, lat)
                    # df['geometry'] = Point(lat, long)
                    df2 = df2.append(df, ignore_index=True)  # geodataframe used as output
                    print('\t- ' + ', '.join(query) + ': ' + str(len(df.index)) + ' samples *')
                found[', '.join(query)] = coord
            else:
                df2 = df2.append(df, ignore_index=True)  # geodataframe used as output
                if ', '.join(query) not in notfound:
                    notfound.append(', '.join(query))

    # print(df2.head())

    if len(notfound) > 0:
        print('\nWARNING!\nCoordinates for these entries were not found.\n'
              'These entries may need to have their coordinates assigned manually, or their names may need to be fixed.\n')
        for entry in notfound:
            print('\t- ' + entry)

    # print(df3)

    if cache not in [None, '']:
        if 'place' in df3.columns.tolist():
            df3 = df3.drop(columns=['place', 'coordinates'])
        df3.to_csv(cache, sep='\t', index=False)


    if fix_projection == 'yes':
        geodf = geodf.to_crs(epsg=4326)
        # get CRS info
        if df2.crs != geodf.crs:
            # print(df2.crs)
            # print(geodf.crs)
            projection = int(str(geodf.crs).split(':')[1])
            # print(projection)
            if df2.crs == None:
                df2 = df2.set_crs(epsg=projection)
            else:
                df2 = df2.to_crs(epsg=projection)
            # print(df2.crs)
            # print(geodf.crs)

    # print(df2.head())
    # print(geodf.head())

    # find shapes where points are located
    results = gpd.sjoin(df2, geodf, how='left', op='within')
    target_cols = [c.strip() for c in target_cols.split(',')]
    if same_file == 'yes':
        output_cols = df1.columns.tolist() + target_cols
    else:
        output_cols = geo_cols + [lat_col, long_col] + target_cols # filter columns

    # print(results.head())
    results = results[output_cols]

    # print(results)
    # override and fill empty state data points
    # df1['ADM1_PT'] = df1['state'].apply(lambda x: state_codes[x] if x in state_codes else x)

    def similar(a, b):
        return SequenceMatcher(None, a, b).ratio()

    mismatches = []
    if check_col not in [None, '']:
        for id2, row2 in results.iterrows():
            # print(results[last_level])
            orig_name = results.loc[id2, last_level]
            new_name = results.loc[id2, check_col]
            # print(orig_name, ' >>> ', new_name, ':', str(similar(orig_name, new_name)))
            if len(str(new_name)) <= 4:
                threshold = 0.65
            if similar(str(orig_name).lower(), str(new_name).lower()) < threshold:
                # print(orig_name, ' >>> ', new_name, ':', str(similar(orig_name, new_name)))
                entry = str(orig_name) + ' > ' + str(new_name)
                if entry not in mismatches:
                    mismatches.append(entry)
                # results = results.drop(id2)

    if len(mismatches) > 0:
        print('\nWARNING!\nMismatches between the original location names and names in shapefiles were detected.\n'
              'These entries may need to have their coordinates assigned manually, or their names may need to be fixed.\n')
        for entry in mismatches:
            print('\t' + entry)

    # output updated dataframe
    if output_coordinates != 'yes':
        results = results.drop(columns=['lat', 'long'])
    results.to_csv(output, sep='\t', index=False)
    print('\nLocation names successfully matched to shapefile.\n\t- Output was saved :%s\n' % output)



    # geodf.plot()
    # import matplotlib.pyplot as plt
    # plt.show()
