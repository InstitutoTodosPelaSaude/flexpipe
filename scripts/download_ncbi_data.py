# -*- coding: utf-8 -*-

from Bio import Entrez
from Bio import SeqIO
import time
import numpy as np
import argparse
import pandas as pd
import pycountry_convert as pcc
import pycountry
import os

Entrez.email = "youremail@email.com"

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Fetch sequenced West Nile Virus genomes from NCBI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--fasta", required=False, help="Existing FASTA file with previously downloaded sequences")
    parser.add_argument("--metadata", required=False, help="Existing TSV metadata file generated previouly by this script")
    parser.add_argument("--taxid", required=True, type=int, help="NCBI Taxonomy ID (e.g. Dengue virus 2 = 11060)")
    parser.add_argument("--genome-size", required=True, type=int, help="Reference genome size (in nucleotides")
    parser.add_argument("--min-size", required=False, type=str, help="Minimum genome size (in nucleotides or proportion as float)")
    parser.add_argument("--max-size", required=False, type=str, help="Maximum genome size (in nucleotides or proportion as float)")
    parser.add_argument("--get-sequences", required=False, type=str, default='yes',
                        choices=['yes', 'no'], help="Should sequences be downloaded in this run: yes or no?")
    parser.add_argument("--get-metadata", required=False, type=str, default='yes',
                        choices=['yes', 'no'], help="Should metadata be downloaded in this run: yes or no?")
    parser.add_argument("--mode", required=False, nargs=1, type=str,  default='mock', choices=['separate', 'append', 'mock'],
                        help="How the output will be exported? As a separate file, or appending to an existing file?")
    parser.add_argument("--output1", required=False, help="Output fasta file")
    parser.add_argument("--output2", required=False, help="Output TSV metadata file")

    args = parser.parse_args()
    sequences = args.fasta
    metadata = args.metadata
    txid = str(args.taxid)
    genome_size = args.genome_size
    min_size = str(args.min_size)
    max_size = str(args.max_size)
    get_sequences = args.get_sequences
    get_metadata = args.get_metadata
    how = args.mode[0]
    output1 = args.output1
    output2 = args.output2


    # path = '/Users/Anderson/Library/CloudStorage/GoogleDrive-anderson.brito@itps.org.br/Outros computadores/My Mac mini/google_drive/ITpS/projetos_colaboracoes/nextstrain/pipeline/flexpipe/data/'
    # sequences = path + 'sequences_ncbi.fasta'
    # metadata = path + 'metadata_ncbi.tsv'
    # txid = str(11089)
    # genome_size = 10862
    # min_size = str(0.7)
    # max_size = str(1.1)
    # get_sequences = 'yes'
    # get_metadata = 'yes'
    # how = 'separate'
    # output1 = path + 'ncbi_sequences2.fasta'
    # output2 = path + 'metadata_ncbi2.tsv'


    # minimum genome size
    if min_size not in [None, '']:
        if '.' in min_size:
            min = str(genome_size * float(min_size))
        else:
            min = str(min_size)
    else:
        min = str(genome_size * 0.7)

    # maximum genome size
    if max_size not in [None, '']:
        if '.' in max_size:
            max = str(genome_size * float(max_size))
        else:
            max = str(max_size)
    else:
        max = str(genome_size * 0.7)


    print('\nDownloading NCBI data (sequences from ' + str(int(float(min))) + ' bp to ' + str(int(float(max))) + ' bp).')


    if how == 'append':
        output1 = sequences
        output2 = metadata
    elif how == 'separate':
        if output1 in [None, ''] or output2 in [None, '']:
            if sequences in [None, ''] or metadata in [None, '']:
                output1 = 'sequences.fasta'
                output2 = 'metadata.tsv'
            else:
                output1 = sequences.split('.')[0] + '_extra.fasta'
                output2 = metadata.split('.')[0] + '_extra.tsv'


    # existing ncbi fasta file
    existing_sequences = []
    if sequences != None:
        cmd = 'grep \"^>\" \"' + sequences + '\" | sed \'s/>//g\' > seqlist.txt'
        os.system(cmd)
        existing_sequences = list(set([header.replace('hCoV-19/', '').split('|')[0].replace(' ', '').strip() for header in open('seqlist.txt').readlines()]))
        os.system('rm seqlist.txt')


    dfR = pd.DataFrame(columns=['genbank'])
    if metadata != None:
        dfR = pd.read_csv(metadata, encoding='utf-8', sep='\t', dtype=str)


    # print(txid, min, max)
    # inspect = Entrez.esearch(db="nucleotide", term="txid2697049[Organism] 25000:35000[SLEN]", idtype="acc")
    query = "txid%s[Organism] %s:%s[SLEN]" % (txid, min, max)
    inspect = Entrez.esearch(db="nucleotide", term=query, idtype="acc")
    total_entries = int(Entrez.read(inspect)['Count'])
    # print(total_entries)

    # convert state code to name
    state_names = {}
    def code2name(country, accronym):
        if country + '-' + accronym not in state_names:
            alpha2 = pcc.country_name_to_country_alpha2(country, cn_name_format="default")
            query = alpha2 + '-' + accronym
            result = pycountry.subdivisions.get(code=query).name
            state_names[country + '-' + accronym] = result
            return result
        else:
            return state_names[country + '-' + accronym]

    # open output file
    if how == 'separate': # save in a separate file
        outfile1 = open(output1, 'w')
        outfile1.write('')

    elif how == 'append':
        outfile1 = open(sequences, 'a')
        outfile1.write('')
        # outfile2 = metadata
    else:
        print('\nNo output will be generated (mock run)\n')


    ### START NCBI SEARCH

    start_at = 1
    notFound = []
    today = time.strftime('%Y-%m-%d', time.gmtime())

    # export new NCBI entries
    # skip_extra = open(skip, 'a')
    comment = ''

    dfM = pd.DataFrame()
    if total_entries > 1000:
        c = 1
        for num in range(1, int(np.ceil(total_entries/1000)) + 1):
            print('\n>>> Retrieving cycle ' + str(num))
            handle = Entrez.esearch(db="nucleotide", retstart=start_at, retmax=1000,
                                    term=query, idtype="acc")
            record = Entrez.read(handle)
            start_at = num * 1000 # define the rounds of search

            previous = 1
            count = 1
            seq_search_list = [accno.split('.')[0] for accno in record['IdList'] if accno.split('.')[0] not in existing_sequences]
            # print(seq_search_list)

            met_search_list = [accno.split('.')[0] for accno in record['IdList'] if accno.split('.')[0] not in dfR['genbank'].tolist()]
            # print(met_search_list)

            search_list = list(set(seq_search_list + met_search_list))

            excluded = [accno.split('.')[0] for accno in record['IdList'] if accno.split('.')[0] not in search_list]
            c += len(excluded)

            if len(excluded) > 0:
                print('A total of ' + str(len(excluded)) + ' entries were already present in the existing datasets.')
            for accno in search_list:#[245:250]:
                print('\n' + str(c) + '/' + str(total_entries))

                accno = accno.split('.')[0]
                new_row = {} # to update metadata dataframe

                current = time.time()
                delay = 0.4
                elapsed = current - previous
                wait = delay - elapsed

                try:

                    handle = Entrez.efetch(db="nucleotide", id=accno, rettype="gb", retmode="text")
                    genome, genbank, date, country, division, location, length, host, authors, date_submitted = ['' for x in range(10)]

                    sequence = ''
                    for seq_record in SeqIO.parse(handle, "gb"):
                        if get_sequences == 'yes':
                            sequence = str(seq_record.seq) # genome sequence

                            if accno not in existing_sequences: # avoiding duplicates
                                if how == 'separate':
                                    outfile1.write('>' + accno + '\n' + sequence + '\n')
                                    outfile1.flush()

                                elif how == 'append':
                                    outfile1.write('>' + accno + '\n' + sequence + '\n')
                                    outfile1.flush()
                                existing_sequences.append(accno)
                                print('\t- ' + accno + ': exporting NCBI fasta')
                            else:
                                print('\t- ' + accno + ': genome already downloaded. Skipping... ')


                        if get_metadata == 'yes':
                            if accno not in dfR['genbank'].tolist(): # avoiding duplicates
                                data = {}
                                for feature in seq_record.annotations['references']:
                                    length = str(len(seq_record.seq))
                                    authors = feature.authors.split(",")[0] + " et al"
                                    if feature.title =='Direct Submission':
                                        date_submitted = pd.to_datetime(feature.journal.split('(')[1].split(')')[0]).strftime('%Y-%m-%d')
                                        # print(date_submitted)

                                for feature in seq_record.features:
                                    if feature.type == 'source':
                                        try:
                                            date = feature.qualifiers['collection_date'][0]
                                            # print(date)
                                            if len(date) > 7:
                                                date = pd.to_datetime(date).strftime('%Y-%m-%d')
                                            elif len(date) == 4:
                                                date = date + '-XX-XX'
                                            elif len(date) == 7:
                                                date = date + '-XX'
                                        except:
                                            pass
                                        try:
                                            origin = feature.qualifiers['country'][0]
                                            if ':' in origin:
                                                country = origin.split(":")[0]
                                                if len(origin.split(":")) > 0:  # get subnational location information
                                                    subnational = origin.split(":")[1]
                                                    if ',' in subnational:
                                                        division = subnational.split(',')[0].strip()
                                                        location = subnational.split(',')[1].strip()
                                                    else:
                                                        division = subnational.strip()
                                            else:
                                                country = origin
                                        except:
                                            pass
                                        try:
                                            if len(division) == 2:
                                                division = code2name(country, division)
                                        except:
                                            pass
                                        try:
                                            host = feature.qualifiers['host'][0]
                                        except:
                                            pass


                                data = {'id': accno, 'genbank': accno, 'date': date, 'country': country, 'division': division,
                                        'location': location, 'length': length, 'host': host, 'authors': authors,
                                        'date_submitted': date_submitted}
                                new_row.update(data)

                                # create an output dataframe
                                if len(dfR.columns.tolist()) == 1 and dfM.empty: # no existing metadata provided
                                    dfM = pd.DataFrame(columns=list(data.keys()))
                                else:
                                    if dfM.empty and how == 'append': # cache metadata provided, append as output
                                        dfM = dfR
                                    elif dfM.empty and how == 'separate': # cache metadata provided, blank DF as output
                                        dfM = pd.DataFrame(columns=list(data.keys()))

                                # dfM = dfM.append(new_row, ignore_index=True)
                                # print(new_row)

                                new_row = {k: [v] for k, v in new_row.items()}  # WORKAROUND
                                dfS = pd.DataFrame(new_row)
                                frames = [dfM, dfS]
                                dfM = pd.concat(frames).reset_index(drop=True)
                                # print(dfM)
                                dfM.to_csv(output2, sep='\t', index=False, header=True, mode='w')

                                print('\t- ' + accno + ': ' + 'exporting NCBI metadata')

                            else:
                                print('\t- ' + accno + ': metadata already downloaded. Skipping... ')

                except:
                    print("\t- " + accno + ": entry not found on NCBI, or backend searching failed")
                    notFound.append(accno)

                previous = time.time()
                count += 1
                c += 1


    # list entries not found on NCBI
    if len(notFound) > 0:
        print('\nThe following genomes were not retrieved:\n')
        for entry in notFound:
            print('\t' + entry)



