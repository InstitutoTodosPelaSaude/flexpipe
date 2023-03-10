# coding=utf-8
#!/usr/bin/python

# Created by: Anderson Brito
# Email: andersonfbrito@gmail.com
# Release date: 2020-03-24
# Last update: 2023-03-03

import pandas as pd
from geopy.geocoders import Nominatim
import argparse
import numpy as np

geolocator = Nominatim(user_agent="email@gmail.com")  # add your email here

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Generate file with latitudes and longitudes of samples listed in a metadata file",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--metadata", required=True, help="Nextstrain metadata file")
    parser.add_argument("--columns", nargs='+', type=str, help="list of columns that need coordinates")
    parser.add_argument("--cache", required=False, help="TSV file with pre-processed latitudes and longitudes")
    parser.add_argument("--output", required=True, help="TSV file containing geographic coordinates")
    args = parser.parse_args()

    metadata = args.metadata
    columns = args.columns
    cache = args.cache
    output = args.output

    # metadata = path + 'results/final_metadata.tsv'
    # # geoscheme = path + "geoscheme.tsv"
    # columns = ['country', 'division', 'location']
    # cache = path + 'config/cache_coordinates.tsv'
    # output = path + 'config/latlongs.tsv'

    force_coordinates = {'Washington DC': ('38.912708', '-77.009223')}


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

    # open metadata file as dataframe
    dfN = load_table(metadata)
    dfN.fillna('', inplace=True)

    results = {trait: {} for trait in columns}  # content to be exported as final result

    # extract coordinates from cache file
    if cache not in ['', None]:
        for line in open(cache).readlines():
            if not line.startswith('\n'):
                try:
                    trait, place, lat, long = line.strip().split('\t')
                    if trait in results.keys():
                        entry = {place: (str(lat), str(long))}
                        results[trait].update(entry)  # save as pre-existing result
                except:
                    pass


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


    queries = []
    pinpoints = [dfN[trait].values.tolist() for trait in columns if trait != 'region']
    for address in zip(*pinpoints):
        traits = [trait for trait in columns if trait != 'region']
        for position, place in enumerate(address):
            level = traits[position]
            query = list(address[0:position + 1])
            queries.append((level, query))


    not_found = []
    for unknown_place in queries:
        # print(unknown_place)
        trait, place = unknown_place[0], unknown_place[1]
        target = place[-1]
        if target not in ['', 'NA', 'NAN', 'unknown', '-', np.nan, None]:

            if target not in results[trait]:
                new_query = []
                for name in place:
                    if name not in new_query:
                        new_query.append(name)

                item = (trait, ', '.join(new_query))
                coord = ('NA', 'NA')
                # print(item)
                if item not in not_found:
                    coord = find_coordinates(', '.join(new_query))  # search coordinates
                if 'NA' in coord:
                    if item not in not_found:
                        not_found.append(item)
                        print('\t* WARNING! Coordinates not found for: ' + trait + ', ' + ', '.join(new_query))
                else:
                    print('\t→ ' + trait + ', ' + target + '. Coordinates = ' + ', '.join(coord))
                    entry = {target: coord}
                    results[trait].update(entry)


    print('\n### These coordinates were found and saved in the output file:')
    with open(output, 'w') as outfile:
        for trait, lines in results.items():
            print('\n* ' + trait)
            for place, coord in lines.items():
                if place in force_coordinates:
                    lat, long = force_coordinates[place][0], force_coordinates[place][1]
                else:
                    lat, long = coord[0], coord[1]
                print('\t→ ' + place + ': ' + lat + ', ' + long)
                line = "{}\t{}\t{}\t{}\n".format(trait, place, lat, long)
                outfile.write(line)
            outfile.write('\n')

    if len(not_found) > 1:
        print('\n### WARNING! Some coordinates were not found (see below).'
              '\nTypos or especial characters in place names my explain such errors.'
              '\nPlease fix them, and run the script again, or add coordinates manually:\n')
        for trait, address in not_found:
            print('\t→ ' + trait + ': ' + address)

print('\nCoordinates file successfully created!\n')
