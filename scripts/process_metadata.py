# -*- coding: utf-8 -*-

# Created by: Anderson Brito
# Email: andersonfbrito@gmail.com
# Release date: 2020-03-24
# Last update: 2023-03-02


import pycountry_convert as pyCountry
import pycountry
from Bio import SeqIO
import pandas as pd
import time
import argparse

pd.set_option('display.max_columns', 500)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Process metadata files re-formmating and exporting selected samples",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--sequences", required=True, help="FASTA file")
    parser.add_argument("--metadata1", required=True, help="Metadata file")
    parser.add_argument("--metadata2", required=False, help="New metadata file")
    parser.add_argument("--time-var", required=False, type=str, help="Time variable, when x variable is not temporal data")
    parser.add_argument("--start-date", required=False, type=str,  help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end-date", required=False, type=str,  help="End date in YYYY-MM-DD format")
    parser.add_argument("--filter1", required=False, type=str, help="Filter for contextual metadata. Format: '~column_name:value'. Remove '~' to keep only that data category")
    parser.add_argument("--filter2", required=False, type=str, help="Filter for new metadata. Format: '~column_name:value'. Remove '~' to keep only that data category")
    parser.add_argument("--output1", required=True, help="Final metadata file")
    parser.add_argument("--output2", required=True, help="Final FASTA file")
    parser.add_argument("--output3", required=False, help="IQTree renaming list")
    args = parser.parse_args()

    genomes = args.sequences
    metadata1 = args.metadata1
    metadata2 = args.metadata2
    timevar = args.time_var
    start_date = args.start_date
    end_date = args.end_date
    filter1 = args.filter1
    filter2 = args.filter2
    output1 = args.output1
    output2 = args.output2
    output3 = args.output3

    # path = '/Users/Anderson/Library/CloudStorage/GoogleDrive-anderson.brito@itps.org.br/Outros computadores/My Mac mini/google_drive/ITpS/projetos_colaboracoes/nextstrain/pipeline/flexpipe/'
    # genomes = path + 'results/temp_dataset.fasta'
    # metadata1 = path + 'data/metadata.tsv'
    # metadata2 = path + 'data/new_metadata.xlsx'
    # timevar = 'date'
    # start_date = '' # start date above this limit
    # end_date = '' # end date below this limit
    # filter1 = "division:São Paulo"
    # filter2 = 'location:Caraguatatuba'
    # output1 = path + 'results/final_metadata.tsv'
    # output2 = path + 'results/final_sequences.fasta'
    # output3 = path + "results/rename.tsv"


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


    # get ISO alpha3 country codes
    isos = {'': ''}
    def get_iso(country):
        global isos
        if country not in isos.keys():
            try:
                isoCode = pyCountry.country_name_to_country_alpha3(country, cn_name_format="default")
                isos[country] = isoCode
            except:
                try:
                    isoCode = pycountry.countries.search_fuzzy(country)[0].alpha_3
                    isos[country] = isoCode
                except:
                    isos[country] = ''
        return isos[country]

    # contextual metadata
    dfN = load_table(metadata1)
    dfN.insert(4, 'country_code', '')
    dfN.fillna('', inplace=True)

    # Lab genomes metadata
    dfE = load_table(metadata2)
    dfE.fillna('', inplace=True)

    # filter by date
    def filter_bydate(df, start, end):
        today = time.strftime('%Y-%m-%d', time.gmtime())
        df[timevar] = df[timevar].str.replace('/', '-', regex=False)

        # assess date completeness
        df = df[df[timevar].apply(lambda x: len(x.split('-')) == 3)]  # accept only full dates
        df = df[df[timevar].apply(lambda x: 'X' not in x)] # exclude -XX-XX missing dates

        df[timevar] = pd.to_datetime(df[timevar])  # converting to datetime format
        if start in [None, '']:
            start = df[timevar].min().strftime('%Y-%m-%d')
        if end in [None, '']:
            end = today

        print('\t- Filtering data by ' + '\"' + timevar + '\": ' + start + ' > ' + end)
        mask = (df[timevar] >= start) & (df[timevar] <= end)  # mask any lines with dates outside the start/end dates
        df = df.loc[mask]  # apply mask
        df[timevar] = df[timevar].dt.strftime('%Y-%m-%d')
        return df


    if timevar not in ['', None]:
        print('\nFiltering rows by date...')
        dfN = filter_bydate(dfN, start_date, end_date)
        dfE = filter_bydate(dfE, start_date, end_date)


    # filter rows by parameters
    def filter_df(df, criteria):
        print('\nFiltering rows by user-defined parameters...')
        # print(criteria)
        new_df = pd.DataFrame()
        include = {}
        for filter_value in criteria.split(','):
            filter_value = filter_value.strip()
            if not filter_value.startswith('~'):
                col, val = filter_value.split(':')[0], filter_value.split(':')[1]
                if val == '\'\'':
                    val = ''
                if col not in include:
                    include[col] = [val]
                else:
                    include[col].append(val)

        # print('Include:', include)
        for filter_col, filter_val in include.items():
            print('\t- Including only rows with \'' + filter_col + '\' = \'' + ', '.join(filter_val) + '\'')
            if new_df.empty:
                df_filtered = df[df[filter_col].isin(filter_val)]
                frames = [new_df, df_filtered]
                new_df = pd.concat(frames, ignore_index=True)
            else:
                new_df = new_df[new_df[filter_col].isin(filter_val)]

        exclude = {}
        for filter_value in criteria.split(','):
            filter_value = filter_value.strip()
            if filter_value.startswith('~'):
                # print('\t- Excluding all rows with \'' + col + '\' = \'' + val + '\'')
                filter_value = filter_value[1:]
                col, val = filter_value.split(':')[0], filter_value.split(':')[1]
                if val == '\'\'':
                    val = ''
                if col not in exclude:
                    exclude[col] = [val]
                else:
                    exclude[col].append(val)

        # print('Exclude:', exclude)
        for filter_col, filter_val in exclude.items():
            print('\t- Excluding all rows with \'' + filter_col + '\' = \'' + ', '.join(filter_val) + '\'')
            if new_df.empty:
                df = df[~df[filter_col].isin(filter_val)]
                frames = [new_df, df]
                new_df = pd.concat(frames, ignore_index=True)
            else:
                new_df = new_df[~new_df[filter_col].isin(filter_val)]
        return new_df


    # load filter data
    if filter1 not in ['', None]:
        if ':' not in filter1:
            dfC = load_table(filter1)
            dfC['action'] = dfC['action'].apply(lambda x: '~' if x == 'exclude' else '')  # exclude -XX-XX missing dates
            dfC['filter'] = dfC['action'].astype(str) + dfC['column'].astype(str) + ':' + dfC['value'].astype(str)
            filter1 = ', '.join(dfC['filter'].tolist())
        if filter1 == '':
            pass
        else:
            dfN = filter_df(dfN, filter1)
    # print(dfN)

    # load filter data
    if filter2 not in ['', None]:
        if ':' not in filter2:
            dfC = load_table(filter2)
            dfC['action'] = dfC['action'].apply(lambda x: '~' if x == 'exclude' else '')  # exclude -XX-XX missing dates
            dfC['filter'] = dfC['action'].astype(str) + dfC['column'].astype(str) + ':' + dfC['value'].astype(str)
            filter2 = ', '.join(dfC['filter'].tolist())
        if filter2 == '':
            pass
        else:
            dfE = filter_df(dfE, filter2)

    # list of sequences included in the new metadata
    new_sequences = dfE['strain'].tolist()
    # print(dfE)

    # list of relevant genomes sequenced
    keep_only = dfE['strain'].tolist()
    excluded = [id for id in new_sequences if id not in keep_only]

    # create a dict of existing sequences
    sequences = {}
    for fasta in SeqIO.parse(open(genomes), 'fasta'):  # as fasta:
        id, seq = fasta.description, fasta.seq
        if id not in sequences.keys() and id not in excluded:
            sequences[id] = str(seq)

    # print(dfN)

    # fix column inconsistencies between metadata files
    metadata1_columns = dfN.columns.values  # list of column in the original metadata file
    for col in metadata1_columns:
        if col not in dfE.columns:
            dfE[col] = ''

    # output dataframe
    found = []
    outputDF = pd.DataFrame(columns=metadata1_columns)

    # process contextual metadata
    dfN = dfN[dfN['strain'].isin(sequences.keys())] # filter only samples included in fasta file
    for idx, row in dfN.iterrows():
        # print(row)
        strain = dfN.loc[idx, 'strain']#.replace('hCoV-19/', '')
        # print(strain)

        if strain in sequences:
            if strain in outputDF['strain'].to_list():
                continue
            dict_row = {}
            date = ''
            for col in metadata1_columns:
                if col == 'date':
                    date = dfN.loc[idx, col]
                dict_row[col] = ''
                if col in row:
                    dict_row[col] = dfN.loc[idx, col]

            dict_row['country_code'] = get_iso(dict_row['country'])
            found.append(strain)

            dfR = pd.DataFrame([dict_row])
            # print(dfR)
            frames = [outputDF, dfR]
            outputDF = pd.concat(frames, ignore_index=True)
    # print(outputDF)

    # process metadata from newly sequenced samples
    metadata_issues = {}
    new_samples = []
    for idx, row in dfE.iterrows():
        id = dfE.loc[idx, 'strain']#.replace('hCoV-19/', '')
        if id in sequences:
            dict_row = {}
            for col in metadata1_columns:
                dict_row[col] = ''
                if col in row:
                    dict_row[col] = dfE.loc[idx, col].strip()  # add values to dictionary

            # set the strain name
            dict_row['country_code'] = get_iso(dict_row['country'])

            # record sequence and metadata as found
            found.append(id)
            dfR = pd.DataFrame([dict_row])

            # register new samples
            if id not in new_samples:
                new_samples.append(id)

            frames = [outputDF, dfR]
            outputDF = pd.concat(frames, ignore_index=True)

    # print(outputDF)

    # # fix date format
    # outputDF['date'] = pd.to_datetime(outputDF['date']) 
    # outputDF['date'] = outputDF['date'].dt.strftime('%Y-%m-%d')

    # write new metadata files
    outputDF.to_csv(output1, sep='\t', index=False)

    # write sequence file
    # export new metadata lines
    outfile2 = open(output2, 'w')
    outfile3 = open(output3, 'w')
    exported = []

    for id, sequence in sequences.items():
        if id in new_samples: # export newly generated sequences
            if id not in exported:
                entry = '>' + id + '\n' + sequence + '\n'
                outfile2.write(entry)
                new_id = id.replace('/', '_')
                outfile3.write(new_id + '\t' + id + '\n')
                exported.append(id)

        else:  # export contextual sequences
            if id not in exported and id in outputDF['strain'].tolist():
                # print(id)
                entry = '>' + id + '\n' + sequence + '\n'
                outfile2.write(entry)
                new_id = id.replace('/', '_')
                outfile3.write(new_id + '\t' + id + '\n')
                exported.append(id)

    print('\nMetadata file successfully processed and exported!\n')
