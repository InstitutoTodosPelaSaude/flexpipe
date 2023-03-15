# Created by: Anderson Brito
# Email: andersonfbrito@gmail.com
# Release date: 2023-01-11
# Last update: 2023-03-15


import pandas as pd
import argparse
from bs4 import BeautifulSoup as BS
import numpy as np
from pylab import *
from colour import Color

import warnings
# warnings.simplefilter(action='ignore', category=FutureWarning)
# warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Collapse groups of two or more rows, summing up corresponding values in matrix",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--input", required=True, help="TSV file with categorical data to be assigned with colours")
    parser.add_argument("--colours", required=True, help="TSV file with the highest level category names and their assigned hue numbers (from 0 to 350), or matplotlib colormap names")
    parser.add_argument("--levels", required=True, nargs='+', type=str, help="List of column names with categorical data, in hierarchical order.")
    parser.add_argument("--output", required=True, help="Final output with colour schemes in TSV format")
    args = parser.parse_args()

    input = args.input
    colours = args.colours
    levels = args.levels
    output = args.output


    # path = "/Users/anderson/google_drive/ITpS/projetos_itps/vigilanciagenomica/analyses/relatorioXX_20221025/figures/colours/"
    # path = "/Users/Anderson/Library/CloudStorage/GoogleDrive-anderson.brito@itps.org.br/Outros computadores/My Mac mini/google_drive/ITpS/projetos_itps/vigilanciagenomica/analyses/relatorioXX_20221107/figures/colours/"
    # path = "/Users/anderson/google_drive/ITpS/projetos_itps/vigilanciagenomica/analyses/relatorioXX_20220812/data/"
    # input = path + "mock_data.tsv"
    # input = path + "metadata_cli.tsv"
    # grid = path + 'colour_grid.html'
    # list_hues = {'North America': ['blue'], 'South America': ['red']}
    # colour_wheel = {'North America': 'Blues_r', 'South America': 'Reds_r', 'Europe': '50'}
    # colour_wheel = {'Alpha': '330', 'Beta': '310', 'Delta': '0', 'Omicron/1': '30', 'Omicron/2': '40',
    #                 'Omicron/3': '70', 'Omicron/4': '120', 'Omicron/5': '270', 'Recombinante': '180', 'Outras': 'Greys_r'}
    # colours = path + 'category_hues.tsv'
    # levels = ['who_variant', 'pango_lineage', 'variant_lineage']
    # output = path + 'colours.tsv'


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


    # open dataframe
    df = load_table(input)
    df.fillna('', inplace=True)
    df = df[~df[levels[0]].isin([''])]

    dfC = load_table(colours)
    colour_wheel= {}
    for idx, row in dfC.iterrows():
        key = dfC.loc[idx, 'category']
        value = dfC.loc[idx, 'hue']
        colour_wheel[key] = value

    # print(colour_wheel)

    ''' GENERATE COLOUR SCHEME '''

    def linear_gradient(start_hex, finish_hex, n):
        start = Color(start_hex)
        end = Color(finish_hex)
        colors = list(start.range_to(end, n))
        colors = [c.hex_l for c in colors]
        # print(colors)
        return colors


    hue_to_hex = {
        0: ('#660000', '#F5D6D6'), 10: ('#661100', '#F5DBD6'), 20: ('#662200', '#F5E0D6'),
        30: ('#663300', '#F5E6D6'), 40: ('#664400', '#F5EBD6'), 50: ('#665500', '#F5F0D6'),
        60: ('#666600', '#F5F5D6'), 70: ('#556600', '#F0F5D6'), 80: ('#446600', '#EBF5D6'),
        90: ('#336600', '#E6F5D6'), 100: ('#226600', '#E0F5D6'), 110: ('#116600', '#DBF5D6'),
        120: ('#006600', '#D6F5D6'), 130: ('#006611', '#D6F5DB'), 140: ('#006622', '#D6F5E0'),
        150: ('#006633', '#D6F5E6'), 160: ('#006644', '#D6F5EB'), 170: ('#006655', '#D6F5F0'),
        180: ('#006666', '#D6F5F5'), 190: ('#005566', '#D6F0F5'), 200: ('#004466', '#D6EBF5'),
        210: ('#003366', '#D6E6F5'), 220: ('#002266', '#D6E0F5'), 230: ('#001166', '#D6DBF5'),
        240: ('#000066', '#D6D6F5'), 250: ('#110066', '#DBD6F5'), 260: ('#220066', '#E0D6F5'),
        270: ('#330066', '#E6D6F5'), 280: ('#440066', '#EBD6F5'), 290: ('#550066', '#F0D6F5'),
        300: ('#660066', '#F5D6F5'), 310: ('#660055', '#F5D6F0'), 320: ('#660044', '#F5D6EB'),
        330: ('#660033', '#F5D6E6'), 340: ('#660022', '#F5D6E0'), 350: ('#660011', '#F5D6DB')
    }
    # print(hue_to_hex)


    # # output dictionary
    results = {trait: {} for trait in levels}
    for highest, dfG in df[levels].groupby(levels[0], as_index=False):
        # print('\n' + highest)
        dfG = dfG.drop_duplicates().sort_values(by=levels)
        # print(dfG)
        for level in levels:
            members = dfG[level].drop_duplicates().tolist()

            if colour_wheel[highest].isdigit():
                start, end = hue_to_hex[int(colour_wheel[highest])]
                # print(highest, len(members))
                if len(members) == 1:
                    gradient = linear_gradient(start, end, 11)
                    gradient = [list(gradient)[3]]
                elif 1 < len(members) < 5:
                    gradient = linear_gradient(start, end, 11)
                    if len(members) == 2:
                        gradient = [list(gradient)[2], list(gradient)[8]]
                    elif len(members) == 3:
                        gradient = [list(gradient)[1], list(gradient)[5], list(gradient)[9]]
                    else:
                        gradient = [list(gradient)[0], list(gradient)[3], list(gradient)[6], list(gradient)[9]]
                else:
                    gradient = linear_gradient(start, end, len(members))
                for memb, colour in zip(members, gradient):
                    # print(level, memb, colour)
                    results[level].update({memb: colour})
            else:
                if len(members) == 1:
                    memb = members[0]
                    cmap = cm.get_cmap(colour_wheel[highest], 11)
                    rgba = cmap(5)
                    colour = matplotlib.colors.rgb2hex(rgba)
                    # print(level, memb, colour)
                    results[level].update({memb: colour})
                else:
                    cmap = cm.get_cmap(colour_wheel[highest], len(members)+4)
                    for i, memb in zip(range(cmap.N)[2:-2], members):
                        rgba = cmap(i)
                        colour = matplotlib.colors.rgb2hex(rgba)
                        # print(level, memb, colour)
                        results[level].update({memb: colour})


    ''' EXPORT COLOUR FILE '''

    with open(output, 'w') as outfile:
        header = "{}\t{}\t{}\n".format('field', 'value', 'hex_color')
        outfile.write(header)
        for trait, entries in results.items():
            for place, hexcolour in entries.items():
                line = "{}\t{}\t{}\n".format(trait, place, hexcolour.upper())
                outfile.write(line)
            outfile.write('\n')
    print('\nColour file successfully created!\n')
