# -*- coding: utf-8 -*-
#!/usr/bin/python

# Created by: Anderson Brito
# Email: andersonfbrito@gmail.com
# Release date: 2021-01-19
# Last update: 2021-01-21

import pandas as pd
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--metadata1", required=True, help="Metadata file from nextstrain")
    parser.add_argument("--metadata2", required=True, help="Metadata file from GISAID")
    parser.add_argument("--output", required=True, help="Merged metadata file")
    args = parser.parse_args()

    metadata1 = args.metadata1
    metadata2 = args.metadata2
    output = args.output

    # path = '/Users/anderson/GLab Dropbox/Anderson Brito/projects/ncov/ncov_impacc/nextstrain/run8_20210402_impacc/'
    # metadata1 = path + 'output_files/metadata/base_metadata.tsv'
    # metadata2 = path + 'output_files/assured_data/sample_metadata.tsv'
    # output = path + 'output_files/metadata/metadata_merged.tsv'

    separator1 = ''
    if str(metadata1).split('.')[-1] == 'tsv':
        separator1 = '\t'
    elif str(metadata1).split('.')[-1] == 'csv':
        separator1 = ','

    separator2 = ''
    if str(metadata2).split('.')[-1] == 'tsv':
        separator2 = '\t'
    elif str(metadata2).split('.')[-1] == 'csv':
        separator2 = ','


    # nextstrain metadata
    dfN = pd.read_csv(metadata1, encoding='utf-8', sep=separator1, dtype='str')
    dfN.fillna('', inplace=True)
    dfN = dfN.rename(columns={'age': 'admit_age'})

    # Extra metadata
    dfG = pd.read_csv(metadata2, encoding='utf-8', sep=separator2, dtype='str')

    # list_columns = [col for col in dfG.columns.to_list() if col in dfN.columns.to_list()]  # list of columns in common
    # list_columns = list(set(dfG.columns.to_list() + dfN.columns.to_list()))
    # print(list_columns)
    # dfG = dfG[list_columns]

    # merge frames
    frames = [dfN, dfG]
    result = pd.concat(frames)
    result.fillna('', inplace=True)
    result = result.drop_duplicates(subset=['strain'])
    result.to_csv(output, sep='\t', index=False)

    print('\nTSV metadata files successfully merged.\n')
