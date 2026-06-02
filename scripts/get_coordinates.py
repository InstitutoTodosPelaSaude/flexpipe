# coding=utf-8
#!/usr/bin/python

# Created by: Anderson Brito
# Email: andersonfbrito@gmail.com
# Release date: 2020-03-24
# Last update: 2023-03-03
# Fixed: rate-limiting, timeout, incremental cache write (2025)

import os
import pandas as pd
from geopy.geocoders import Nominatim
import argparse
import numpy as np
import time

# Nominatim ToS: unique user_agent + max 1 req/sec
geolocator = Nominatim(user_agent="flexpipe_rsv_nextstrain_build", timeout=10)

RATE_LIMIT_SLEEP = 2.0   # seconds between requests (conservative to stay under ToS)
RATE_LIMIT_429_WAIT = 90.0  # seconds to wait after a 429 before retrying


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

    results = {trait: {} for trait in columns}

    # load cache
    if cache not in ['', None] and os.path.exists(cache):
        for line in open(cache).readlines():
            if not line.startswith('\n'):
                try:
                    trait, place, lat, long = line.strip().split('\t')
                    if trait in results.keys():
                        entry = {place: (str(lat), str(long))}
                        results[trait].update(entry)
                except:
                    pass

    # Map trait level → Nominatim featuretype so division queries return states,
    # not municipalities with the same name (e.g. "Amazonas" in Amapá vs the state).
    FEATURETYPE = {
        'division': 'state',
        'location': 'city',
    }

    def find_coordinates(place, level=None, retries=6):
        """Query Nominatim with rate-limiting and retries."""
        featuretype = FEATURETYPE.get(level)
        for attempt in range(retries):
            try:
                time.sleep(RATE_LIMIT_SLEEP)
                kwargs = {'language': 'en'}
                if featuretype:
                    kwargs['featuretype'] = featuretype
                location = geolocator.geocode(place, **kwargs)
                if location:
                    return (str(location.latitude), str(location.longitude))
                return ('NA', 'NA')
            except Exception as e:
                is_429 = "429" in str(e) or "Too Many" in str(e) or "RateLimited" in type(e).__name__
                wait = RATE_LIMIT_429_WAIT if is_429 else RATE_LIMIT_SLEEP * (2 ** attempt)
                print(f'\t  Attempt {attempt + 1} failed for "{place}": {e}. Retrying in {wait:.1f}s...')
                time.sleep(wait)
        return ('NA', 'NA')

    def write_output(results, output_path, force_coordinates):
        """Write current results to output file."""
        with open(output_path, 'w') as outfile:
            for trait, lines in results.items():
                for place, coord in lines.items():
                    if place in force_coordinates:
                        lat, long = force_coordinates[place]
                    else:
                        lat, long = coord
                    line = "{}\t{}\t{}\t{}\n".format(trait, place, lat, long)
                    outfile.write(line)
                outfile.write('\n')

    # build query list
    queries = []
    pinpoints = [dfN[trait].values.tolist() for trait in columns if trait != 'region']
    for address in zip(*pinpoints):
        traits = [trait for trait in columns if trait != 'region']
        for position, place in enumerate(address):
            level = traits[position]
            query = list(address[0:position + 1])
            queries.append((level, query))

    # deduplicate queries preserving order
    seen = set()
    unique_queries = []
    for q in queries:
        key = (q[0], tuple(q[1]))
        if key not in seen:
            seen.add(key)
            unique_queries.append(q)

    not_found = []
    total_new = 0

    for unknown_place in unique_queries:
        trait, place = unknown_place[0], unknown_place[1]
        target = place[-1]

        if target in ['', 'NA', 'NAN', 'unknown', '-', np.nan, None]:
            continue
        if target in results[trait]:
            continue  # already cached

        new_query = []
        for name in place:
            if name not in new_query:
                new_query.append(name)

        item = (trait, ', '.join(new_query))
        if item in not_found:
            continue

        coord = find_coordinates(', '.join(new_query), level=trait)

        if 'NA' in coord:
            not_found.append(item)
            print('\t* WARNING! Coordinates not found for: ' + trait + ', ' + ', '.join(new_query))
        else:
            print('\t→ ' + trait + ', ' + target + '. Coordinates = ' + ', '.join(coord))
            results[trait][target] = coord
            total_new += 1

            # write incrementally after each find so a crash doesn't lose data
            write_output(results, output, force_coordinates)

            # also update cache file incrementally
            if cache not in ['', None]:
                with open(cache, 'a') as cf:
                    cf.write("{}\t{}\t{}\t{}\n".format(trait, target, coord[0], coord[1]))

    # final write (covers the case where no new coords were found, only cached)
    print('\n### These coordinates were found and saved in the output file:')
    write_output(results, output, force_coordinates)

    for trait, lines in results.items():
        print('\n* ' + trait)
        for place, coord in lines.items():
            lat, long = force_coordinates.get(place, coord)
            print('\t→ ' + place + ': ' + lat + ', ' + long)

    if len(not_found) > 1:
        print('\n### WARNING! Some coordinates were not found (see below).'
              '\nTypos or special characters in place names may explain such errors.'
              '\nPlease fix them, run the script again, or add coordinates manually:\n')
        for trait, address in not_found:
            print('\t→ ' + trait + ': ' + address)

print('\nCoordinates file successfully created!\n')
