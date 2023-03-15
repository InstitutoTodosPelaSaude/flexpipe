# Created by: Anderson Brito
# Email: andersonfbrito@gmail.com
# Release date: 2021-12-29
# Last update: 2023-03-15

import pandas as pd
import argparse
import os
import numpy as np
import unidecode
import time

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Modify dataframe by adding, removing or modifying columns and rows",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--input1", required=True, help="Original dataframe file")
    parser.add_argument("--input2", required=False, help="Files with extra columns to be added or modified, including an index column")
    parser.add_argument("--index", required=False, type=str, help="Column with unique identifiers")
    parser.add_argument("--action", required=False, type=str,
                        choices=['add', 'modify', 'reorder'], help="Action to be executed to filter target taxa")
    parser.add_argument("--mode", required=False, type=str,
                        choices=['columns', 'rows'], help="Elements to be processed: columns or rows?")
    parser.add_argument("--targets", required=False,  help="List of columns or rows to be added, remove or modified."
                                                           "It can be provided as a file, one target per line, or as a comma-separated list of targets.")
    parser.add_argument("--filter", required=False, type=str, help="Format: '~column_name:value'. Remove '~' to keep only that data category")
    parser.add_argument("--date-column", required=False, type=str, help="Time variable, when x variable is not temporal data")
    parser.add_argument("--start-date", required=False, type=str,  help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end-date", required=False, type=str,  help="End date in YYYY-MM-DD format")
    parser.add_argument("--sortby", nargs='+', required=False, type=str, help="List of columns to be used to sort the dataframe")
    parser.add_argument("--output", required=True, help="TSV file with modified datraframe")
    args = parser.parse_args()

    input1 = args.input1
    input2 = args.input2
    index = args.index
    action = args.action
    mode = args.mode
    list_targets = args.targets
    filters = args.filter
    date_col = args.date_column
    start_date = args.start_date
    end_date = args.end_date
    sortby = args.sortby
    output = args.output


    # path = '/Users/anderson/google_drive/Other computers/My Mac mini/google_drive/ITpS/projetos_itps/monkeypox/analyses/20220729_monkeypox_relatório0/SES-SP/'
    # input1 = path + 'MonkeyPox_355030_id_dtsintomas_dtnot_class.xlsx' # target file
    # input2 = path + 'code_description.tsv' # new data file
    # index = 'classificaFim' # index in common between both dataframes
    # action = 'add'
    # mode = 'columns'
    # # list_targets = path + 'columns.tsv' # list of columns
    # list_targets = "category#4"
    # sortby = None
    # filters = None
    # date_col = None
    # start_date = '' # start date above this limit
    # end_date = '' # end date below this limit
    # output = path + 'matrix_fixed.tsv'



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
            df = df[~df[index].isin([''])]  # drop row with empty index
        else:
            print('Wrong file format. Compatible file formats: TSV, CSV, XLS, XLSX')
            exit()
        return df

    # original
    df1 = load_table(input1)
    df1.fillna('', inplace=True)

    if list_targets != None:
        if os.path.isfile(list_targets):
            targets = [item.strip() for item in open(list_targets).readlines()]
        else:
            if ',' in list_targets:
                # print(list_targets)
                targets = [x.strip() for x in list_targets.split(',')]
            else:
                targets = [list_targets]

    # filter by time
    def time_filter(df, time_var, start_date, end_date):
        print('\nFiltering by \"%s\": %s -> %s' % (time_var, start_date, end_date))
        df[time_var] = pd.to_datetime(df[time_var])  # converting to datetime format
        if start_date in [None, '']:
            start_date = df[time_var].min()
        if end_date in [None, '']:
            today = time.strftime('%Y-%m-%d', time.gmtime())
            end_date = today

        mask = (df[time_var] >= start_date) & (df[time_var] <= end_date)  # mask any lines with dates outside the start/end dates
        df = df.loc[mask]  # apply mask
        df[time_var] = df[time_var].dt.strftime('%Y-%m-%d')
        return df

    # filter rows
    def filter_df(df, criteria):
        print('\nFiltering rows...')
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
            # print(new_df.size)
            if new_df.empty:
                df_filtered = df[df[filter_col].isin(filter_val)]
                new_df = new_df.append(df_filtered)
            else:
                new_df = new_df[new_df[filter_col].isin(filter_val)]
            # print(new_df)#.head())

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
                new_df = new_df.append(df)
            else:
                new_df = new_df[~new_df[filter_col].isin(filter_val)]
            # print(new_df)#.head())
        return new_df


    # apply filter
    if filters not in [None, '']:
        print('\nFiltering rows based on user defined filters...')
        if filters not in ['', None]:
            df1 = filter_df(df1, filters)

    # Filter by date
    if date_col not in ['', None]:
        if start_date or end_date not in [None, '']:
            start, end = '', ''
            if start_date not in [None, '']:
                start = start_date.strip()
            if end_date not in [None, '']:
                end = end_date.strip()

            df1 = time_filter(df1, date_col, start, end)



    found = {}
    notfound = {}
    if action == 'add' and mode == 'columns':
        # source of new columns
        if input2 != None:
            df2 = load_table(input2)
            df2.fillna('', inplace=True)
            if len(targets) > 0:
                print('\n# Adding new columns')
                # print(df2.columns.tolist())
                df2 = df2[[index] + [col.split('#')[0] for col in targets]]
                df2 = df2.drop_duplicates(keep='last')

                for colname in targets:
                    position = 0
                    if '#' in colname:
                        position = int(colname.split('#')[1]) - 1
                        colname = colname.split('#')[0]

                    print('\t- ' + str(position + 1) + '. ' + colname)
                    dict_target = pd.Series(df2[colname].values, index=df2[index]).to_dict()
                    # print(dict_target)

                    # add column
                    df1.insert(position, colname, '')
                    df1[colname] = df1[index].apply(lambda x: dict_target[x] if x in dict_target else '')



    if action == 'modify' and mode == 'rows':
        # source of new data
        df2 = ''
        if input2 != None:
            df2 = load_table(input2)
            # df2 = pd.read_csv(path + input2, encoding='utf-8', sep='\t', dtype=str)
            df2.fillna('', inplace=True)
        else:
            print('File with reference values to be modified is missing. Provide \'--input2\'')
            exit()

        for id2, row2 in df2.iterrows():
            ref_col, ref_val, target_col, fixed_val = df2.loc[id2, 'reference_column'], df2.loc[id2, 'reference_value'], df2.loc[id2, 'target_column'], df2.loc[id2, 'fixed_value']
            # print(ref_col, ref_val, target_col, fixed_val)
            # print(ref_val, df1[ref_col].tolist())
            if ref_val in df1[ref_col].tolist():
                df1.loc[df1[ref_col] == ref_val, target_col] = fixed_val
                if target_col not in found:
                    found[target_col] = [fixed_val]
                else:
                    if fixed_val not in found[target_col]:
                        found[target_col] += [fixed_val]
            else:
                if ref_col not in notfound:
                    if fixed_val not in found[target_col]:
                        notfound[ref_col] = [ref_val]
                else:
                    if ref_val not in notfound[ref_col]:
                        if fixed_val not in found[target_col]:
                            notfound[ref_col] += [ref_val]


    if action == 'reorder' and mode == 'columns':
        if len(targets) > 0:
            print('\n# Reordering columns as follows:')
            for col in targets:
                print('\t- ' + col)
            df1 = df1[targets]

    if len(found.keys()) > 0:
        print('\n# Fixed data points')
        for col, vals in found.items():
            print('  > ' + col)
            for v in vals:
                print('\t- ' + v)
    if len(notfound.keys()) > 0:
        print('\n# These reference data points where not found, and their actions were not implemented:')
        for col, vals in notfound.items():
            print('  > ' + col)
            for v in vals:
                print('\t- ' + v)

    # sort values
    if sortby != None:
        df1 = df1.sort_values(by=sortby)

    df1.to_csv(output, sep='\t', index=False)

