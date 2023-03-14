rule all:
	input:
		auspice = "auspice/results.json",

# Triggers the data and metadata preparation steps
rule prepare:
	input:
		"results/final_metadata.tsv",
		"results/final_dataset.fasta",
		"config/latlongs.tsv",
		"config/colour_scheme.tsv"


# Define file names
rule files:
	params:
		contextual_sequences = "data/sequences.fasta",
		new_sequences = "data/new_sequences.fasta",
		aligned = "config/aligned.fasta",
		metadata = "data/metadata.tsv",
		new_metadata = "data/new_metadata.xlsx",
		cache = "config/cache_coordinates.tsv",
		lat_longs = "config/latlongs.tsv",
		colscheme = "config/name2hue.tsv",
		keep = "config/keep.txt",
		ignore = "config/ignore.txt",
		reference = "config/reference.gb",
		clades = "config/clades.tsv",
		auspice_config = "config/auspice_config.json",


# Define parameters
rule parameters:
	params:
		mask_5prime = 142,
		mask_3prime = 548,
		bootstrap = 1, # default = 1, but ideally it should be >= 100
		model = "GTR",
		root = "JF912185", # set one or more genomes to root the phylogeny
		clock_rate = 0.0003,
		clock_std_dev = 0.0001,

rule options:
	params:
		threads = 1


options = rules.options.params
files = rules.files.params
parameters = rules.parameters.params

rule add_sequences:
	message:
		"""
		Filtering sequence files to:
		- Add contextual and new sequences
		- Prevent unwanted sequences from being incorporated in the initial dataset.
		"""
	input:
		genomes = files.contextual_sequences,
		new_sequences = files.new_sequences,
		include = files.keep,
		exclude = files.ignore
	output:
		sequences = temp("results/temp_dataset.fasta")
	shell:
		"""
		python scripts/add_new_sequences.py \
			--genomes {input.genomes} \
			--new-genomes {input.new_sequences} \
			--keep {input.include} \
			--remove {input.exclude} \
			--output {output.sequences}
		"""


rule process_metadata:
	message:
		"""
		Processing {input.genomes} and metadata files to:
		- Include only metadata from sequences included in {input.genomes}
		- Process metadata by dropping or adding columns, and fixing specific fields
		"""
	input:
		genomes = rules.add_sequences.output.sequences,
		metadata1 = files.metadata,
		metadata2 = files.new_metadata
	output:
		final_metadata = "results/final_metadata.tsv",
		final_sequences = "results/final_dataset.fasta",
		rename = "results/trees/rename.tsv"
	shell:
		"""
		python scripts/process_metadata.py \
			--sequences {input.genomes} \
			--metadata1 {input.metadata1} \
			--metadata2 {input.metadata2} \
			--time-var "date" \
			--output1 {output.final_metadata} \
			--output2 {output.final_sequences} \
			--output3 {output.rename}
		"""


rule coordinates:
	message:
		"""
		Searching for coordinates (latitudes and longitudes) for samples in {input.metadata}
		"""
	input:
		metadata = rules.process_metadata.output.final_metadata,
		cache = files.cache
	params:
		columns = "country division location"
	output:
		latlongs = "config/latlongs.tsv"
	shell:
		"""
		python scripts/get_coordinates.py \
			--metadata {input.metadata} \
			--columns {params.columns} \
			--cache {input.cache} \
			--output {output.latlongs}

		cp {output.latlongs} config/cache_coordinates.tsv
		"""



rule colours:
	message:
		"""
		Assigning colour scheme for defined columns in {input.matrix}
		"""
	input:
		matrix = rules.process_metadata.output.final_metadata,
		scheme = files.colscheme,
	params:
		host = "host_type host",
		geo = "region division location",
	output:
		colours1 = temp("config/col_hosts.tsv"),
		colours2 = temp("config/col_geo.tsv"),
		colour_scheme = "config/colour_scheme.tsv",
	shell:
		"""
		python scripts/colour_maker.py \
			--input {input.matrix} \
			--colours {input.scheme} \
			--levels {params.host} \
			--output {output.colours1}

		python scripts/colour_maker.py \
			--input {input.matrix} \
			--colours {input.scheme} \
			--levels {params.geo} \
			--output {output.colours2}

		python scripts/multi_merger.py \
			--path "./config" \
			--regex "col_*" \
			--columns "field, value, hex_color" \
			--output {output.colour_scheme}
		"""



### STARTING NEXTSTRAIN ANALYSES ###



### Aligning the sequences using MAFFT
rule align:
	message:
		"""
		Aligning sequences to {input.reference}
		    - gaps relative to reference are considered real
		"""
	input:
		sequences = rules.process_metadata.output.final_sequences,
		aligned = files.aligned,
		reference = files.reference,
	params:
		threads = options.threads
	output:
		alignment = "results/alignments/aligned.fasta"
	shell:
		"""
		augur align \
			--sequences {input.sequences} \
			--reference-sequence {input.reference} \
			--nthreads {params.threads} \
			--output {output.alignment} \
			--remove-reference
		"""

			# --existing-alignment {input.aligned} \

### Masking alignment sites
rule mask:
	message:
		"""
		Mask bases in alignment
		  - masking {params.mask_from_beginning} from beginning
		  - masking {params.mask_from_end} from end
		  - masking other sites: {params.mask_sites}
		"""
	input:
		alignment = rules.align.output.alignment
	params:
		mask_from_beginning = parameters.mask_5prime,
		mask_from_end = parameters.mask_3prime,
		mask_sites = "1" # set here any extra sites to be masked
	output:
		alignment = "results/alignments/masked.fasta"
	shell:
		"""
		python scripts/mask-alignment.py \
			--alignment {input.alignment} \
			--mask-from-beginning {params.mask_from_beginning} \
			--mask-from-end {params.mask_from_end} \
			--mask-sites {params.mask_sites} \
			--output {output.alignment}
		"""


# ### Inferring tree with fewer bootstrap iterations
# rule tree:
# 	message: "Building tree"
# 	input:
# 		alignment = rules.mask.output.alignment
# 	params:
# 		threads = options.threads,
# 	output:
# 		tree = "results/trees/masked.tree"
# 	shell:
# 		"""
# 		augur tree \
# 			--alignment {input.alignment} \
# 			--nthreads {params.threads} \
# 			--output {output.tree}
# 		"""

rule tree:
	message:
		"""
		"Building bootstrap tree"
		"""
	input:
		alignment = rules.mask.output.alignment
	params:
		threads = options.threads,
		bootstrap = parameters.bootstrap,
		model = parameters.model,
	output:
		tree = "results/trees/masked.tree"
	shell:
		"""
		iqtree \
			-s {input.alignment} \
			-b {params.bootstrap} \
			-nt {params.threads} \
			-m {params.model}

		mv results/alignments/masked.fasta.treefile {output.tree}
		"""


## Renaming taxa in bootstrap tree

rule rename:
	message:
		"""
		Renaming taxa in bootstrap tree"
		"""
	input:
		tree = rules.tree.output.tree,
		names = rules.process_metadata.output.rename,
	params:
		format = "tree",
		action = "rename"
	output:
		new_tree = "results/trees/final_tree.tree"
	shell:
		"""
		python scripts/masterkey.py \
			--input {input.tree} \
			--format {params.format} \
			--action {params.action} \
			--list {input.names} \
			--output {output.new_tree}
		"""


### Running TreeTime to estimate time for ancestral genomes

rule refine:
	message:
		"""
		Refining tree
		  - estimate timetree
		  - use {params.coalescent} coalescent timescale
		  - estimate {params.date_inference} node dates
		"""
	input:
		tree = rules.rename.output.new_tree,
		alignment = rules.mask.output.alignment,
		metadata = rules.process_metadata.output.final_metadata
	params:
		root = parameters.root,
		coalescent = "skyline",
		clock_rate = parameters.clock_rate,
		clock_std_dev = parameters.clock_std_dev,
		date_inference = "marginal",
		unit = "mutations"
	output:
		tree = "results/trees/tree.nwk",
		node_data = "results/trees/branch_lengths.json"
	shell:
		"""
		augur refine \
			--tree {input.tree} \
			--alignment {input.alignment} \
			--metadata {input.metadata} \
			--output-tree {output.tree} \
			--output-node-data {output.node_data} \
			--root {params.root} \
			--timetree \
			--coalescent {params.coalescent} \
			--date-confidence \
			--clock-filter-iqd 4 \
			--clock-rate {params.clock_rate} \
			--clock-std-dev {params.clock_std_dev} \
			--divergence-units {params.unit} \
			--date-inference {params.date_inference}
		"""


### Reconstructing ancestral sequences and mutations

rule ancestral:
	message:
		"""
		Reconstructing ancestral sequences and mutations"
		"""
	input:
		tree = rules.refine.output.tree,
		alignment = rules.mask.output.alignment
	output:
		node_data = "results/trees/nt_muts.json"
	params:
		inference = "joint"
	shell:
		"""
		augur ancestral \
			--tree {input.tree} \
			--alignment {input.alignment} \
			--inference {params.inference} \
			--output-node-data {output.node_data}
		"""


## Performing amino acid translation

rule translate:
	message:
		"""
		Translating amino acid sequences"
		"""
	input:
		tree = rules.refine.output.tree,
		node_data = rules.ancestral.output.node_data,
		reference = files.reference,
	output:
		node_data = "results/trees/aa_muts.json"
	shell:
		"""
		augur translate \
			--tree {input.tree} \
			--ancestral-sequences {input.node_data} \
			--reference-sequence {input.reference} \
			--output {output.node_data} \
		"""


### Inferring ancestral locations of genomes

rule traits:
	message: "Inferring ancestral traits for {params.columns!s}"
	input:
		tree = rules.refine.output.tree,
		metadata = rules.process_metadata.output.final_metadata,
	params:
		columns = "division location host_type"
	output:
		node_data = "results/trees/traits.json",
	shell:
		"""
		augur traits \
			--tree {input.tree} \
			--metadata {input.metadata} \
			--output {output.node_data} \
			--columns {params.columns} \
			--confidence
		"""


### Define clades based on sets of mutations

rule clades:
	message: " Labeling clades as specified in config/clades.tsv"
	input:
		tree = rules.refine.output.tree,
		aa_muts = rules.translate.output.node_data,
		nuc_muts = rules.ancestral.output.node_data,
		clades = files.clades
	output:
		clade_data = "results/trees/clades.json"
	shell:
		"""
		augur clades \
			--tree {input.tree} \
			--mutations {input.nuc_muts} {input.aa_muts} \
			--clades {input.clades} \
			--output {output.clade_data}
		"""


### Generating final results for visualisation with auspice

rule export:
	message: "Exporting data files for for auspice"
	input:
		tree = rules.refine.output.tree,
		metadata = rules.process_metadata.output.final_metadata,
		branch_lengths = rules.refine.output.node_data,
		traits = rules.traits.output.node_data,
		nt_muts = rules.ancestral.output.node_data,
		aa_muts = rules.translate.output.node_data,
		colors = rules.colours.output.colour_scheme,
		lat_longs = rules.coordinates.output.latlongs,
		clades = rules.clades.output.clade_data,
		auspice_config = files.auspice_config,
	output:
		auspice = rules.all.input.auspice,
	shell:
		"""
		augur export v2 \
			--tree {input.tree} \
			--metadata {input.metadata} \
			--node-data {input.branch_lengths} {input.traits} {input.nt_muts} {input.aa_muts} {input.clades} \
			--colors {input.colors} \
			--lat-longs {input.lat_longs} \
			--auspice-config {input.auspice_config} \
			--output {output.auspice}
		"""


### Clearing the working directory (only executed when needed)

rule clean:
	message: "Removing directories: {params}"
	params:
		"config/colour_scheme.tsv",
		"config/latlongs.tsv",
		"config/aligned.fasta.ref.fasta",
		"results",
		"auspice"

	shell:
		"""
		rm -rfv {params}
		"""

rule reset:
	message: "Removing directories: {params}"
	params:
		"results",
		"auspice",
		"data",
		"config/colour_scheme.tsv",
		"config/latlongs.tsv",
		"results/sequence_dataset.fasta",
		"data/rename.tsv"
	shell:
		"""
		rm -rfv {params}
		"""

rule delete:
	message: "Deleting directory: {params}"
	params:
		"data",
		"results"
	shell:
		"rm -rfv {params}"
