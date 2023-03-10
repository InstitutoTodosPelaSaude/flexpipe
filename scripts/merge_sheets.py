# -*- coding: utf-8 -*-

# Created by: Anderson Brito
# Email: andersonfbrito@gmail.com
# Release date: 2020-05-24
# Last update: 2021-06-22


import pandas as pd
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Merge two excel spreadsheets and export .xlxs file",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--sheet1", required=True, help="Spreadsheet file 1")
    parser.add_argument("--sheet2", required=True, help="Spreadsheet file 2")
    parser.add_argument("--index", required=True, default='Sample-ID', type=str,  help="Name of column with unique identifiers")
    parser.add_argument("--output", required=True, help="Merged spreadsheet file")
    args = parser.parse_args()

    sheet1 = args.sheet1
    sheet2 = args.sheet2
    index = args.index
    output = args.output

    # sheet1 = path + 'COVID-19_sequencing.xlsx'
    # sheet2 = path + 'Incoming S drop out samples.xlsx'
    # index = 'Sample-ID'
    # output = path + 'merged_sheet.xlsx'

    # load spreadsheets
    df1 = pd.read_excel(sheet1, index_col=None, header=0, sheet_name=0)
    df1.fillna('', inplace=True)
    df1 = df1[~df1[index].isin([''])] # drop row with empty index

    df2 = pd.read_excel(sheet2, index_col=None, header=0, sheet_name=0)
    df2.fillna('', inplace=True)
    df2 = df2[~df2[index].isin([''])] # drop row with empty index

    # empty matrix dataframe
    columns = [x for x in df1.columns.to_list() if x in df2.columns.to_list()]
    rows = [x for x in df1[index].to_list() if x not in df2[index].to_list()] + df2[index].to_list()
    duplicates = [x for x in df1[index].to_list() if x  in df2[index].to_list()]

    # drop duplicates
    df2 = df2[~df2[index].isin(duplicates)]

    # filter columns
    df1 = df1[columns]
    df2 = df2[columns]

    # filter rows
    df1 = df1[df1[index].isin(rows)]
    df2 = df2[df2[index].isin(rows)]

    # concatenate dataframes
    frames = [df1, df2]
    df3 = pd.concat(frames)
    df3 = df3.astype(str)

    # export Excel sheet
    df3.to_excel(output, index=False)

    print('\nSpreadsheets successfully merged.\n')