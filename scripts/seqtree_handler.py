#!/usr/bin/python

from Bio import Phylo
from Bio import SeqIO
import argparse


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Rename taxa names in tree and sequence files, and prune trees according to list provided by the user",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--input", required=True, help="FASTA or TREE input file to be filtered")
    parser.add_argument("--format", required=True, nargs=1, type=str, default='fasta',
                        choices=['fasta', 'tree'], help="File format")
    parser.add_argument("--action", required=True, nargs=1, type=str,  default='keep',
                        choices=['keep', 'remove', 'rename'], help="Action to be executed to filter target taxa")
    parser.add_argument("--list", required=True, help="List of target taxa or sequences")
    parser.add_argument("--output", required=True, help="Filtered output file")
    args = parser.parse_args()

    input = args.input
    format = args.format[0]
    list = args.list
    action = args.action[0]
    output = args.output


    targets = [target.strip() for target in open(list, "r").readlines() if target[0] not in ['\n', '#']]
    if format == 'tree':
        tree = Phylo.read(input, 'newick')
        print('Starting tree file processing...')
        # rename clade names
        if action == 'rename':
            for clade in tree.find_clades():
                if not clade.is_terminal():
                    clade.confidence = None
                for line in targets:
                    oldName = line.split("\t")[0]
                    newName = line.split("\t")[1].strip()
                    if str(clade.name) == oldName:
                        print('Renaming ' + oldName + ' as ' + newName)
                        clade.name = newName

            Phylo.write([tree], output, 'newick')
            print('\nTree file successfully renamed: \'' + output)


        # keep or remove taxa
        if action in ['keep', 'remove']:
            allTaxa = []
            # to check clade names
            for clade in tree.find_clades():
                if str(clade.name) != 'None':
                    if not str(clade.name)[0].isdigit():
                        allTaxa.append(str(clade.name))

            # list of taxa to prune from tree
            prune = []
            for tax in targets:
                tax = tax.split('\t')[0]
                prune.append(tax.strip())

            if action == 'keep':
                print(action)
                prune = [item for item in allTaxa if item not in prune]

            # if in prune list, targets are removed
            c = 1
            notintree = []
            print('\n### Filtering taxa from tree\n')
            for taxon in prune:
                try:
                    tree.prune(target=taxon)
                    print(str(c) + ' - ' + taxon + ' was filtered')
                    c += 1
                except:
                    print('Taxon ' + taxon + ' was not found in the tree!')
                    notintree.append(taxon)

            if len(notintree) > 0:
                print('\n### Taxa not found in the input tree = ' + str(len(notintree)) + '\n')
                for num, taxon in enumerate(notintree):
                    print('\t* ' + str(num + 1) + ' - ' + taxon)

            # save tree
            Phylo.write([tree], output, 'newick')
            print('\nTree file successfully filtered: \'' + output)



    if format == 'fasta':
        fasta_sequences = SeqIO.parse(open(input), 'fasta')
        print('Starting sequence file processing...')

        # rename sequence names
        if action == 'rename':
            print('\n### Renaming sequences...')
            replacements = {}
            for taxon in targets:
                if len(taxon.split("\t")) == 2:
                    old = taxon.split("\t")[0]
                    new = taxon.split("\t")[1].strip()
                else:
                    old = taxon.split("_")[0]
                    new = taxon.strip()
                replacements[old] = new

            # perform simple renaming
            found = []
            not_found = []
            duplicates = []
            c = 1
            with open(output, 'w') as outfile:
                for fasta in fasta_sequences:
                    id, seq = fasta.description, fasta.seq
                    if id in replacements.keys():
                        if replacements[id] not in found:
                            entry = ">" + replacements[id] + "\n" + str(seq).upper() + "\n"
                            print(str(c) + '. Renamed - ' + replacements[id])
                            outfile.write(entry)
                            found.append(replacements[id])
                            c += 1
                        else:
                            print('Duplicate found: ' + replacements[id])
                            duplicates.append(replacements[id])
                    else:
                        not_found.append(id)

            if len(not_found) > 0:
                print('\n### Total of sequences not found = ' + str(len(not_found)))
                for num, record in enumerate(not_found):
                    print('\t* ' + str(num + 1) + ' - ' + record)

            if len(duplicates) > 0:
                print('\n### Total of duplicates = ' + str(len(duplicates)))
                for num, record in enumerate(duplicates):
                    print('\t* ' + str(num + 1) + ' - ' + record)
            print('\n### A total of ' + str(len(found)) + ' sequences were renamed \n')

        if action in ['keep', 'remove']:
            found = []  # store all found headers
            record_dict = {}
            for fasta in SeqIO.parse(open(input), 'fasta'):
                id, seq = fasta.description, fasta.seq
                if id not in record_dict.keys():
                    record_dict[id] = str(seq)

            count = 1
            with open(output, 'w') as outfile:
                for header in record_dict.keys():
                    if action == 'keep':
                        if header not in found and header in targets:
                            found.append(header)
                            entry = ">" + header + "\n" + str(record_dict[header]).upper() + "\n"
                            outfile.write(entry)
                            print(str(count) + '/' + str(len(targets)) + " - Filtering sequence... " + header)
                            count += 1

                    if action == 'remove':  # remove selected sequences
                        if header not in targets and header not in found:
                            entry = ">" + header + "\n" + str(record_dict[header]).upper() + "\n"
                            outfile.write(entry)
                        else:
                            print(str(count) + '/' + str(len(targets)) + " - Removing sequence... " + header)
                            count += 1
                            found.append(header)

                def Diff(list1, list2):  # compare full list of headers and those found in the previous step. Flag any headers not found
                    notFound = set(list1) - set(list2)
                    return notFound


                leftout = len(Diff(targets, found))
                if leftout > 0:  # if any headers were not found, print warning and headers
                    print("\nWARNING! " + str(leftout) + " sequence(s) not found:")
                    for sequence in Diff(targets, found):
                        print('\t* ' + sequence)
                    print('\nCheck issues reported above!\n')
                else:
                    print("\nDone! " + str(len(targets) - leftout) + " sequences were filtered.\n")
