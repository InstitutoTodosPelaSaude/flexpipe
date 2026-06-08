# Makefile for Sphinx documentation at the `docs' directory
#
# You can set these variables from the command line.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
PAPER         ?=
BUILDDIR      ?= _build

# Internal variables.
PAPEROPT_a4     = -D latex_paper_size=a4
PAPEROPT_letter = -D latex_paper_size=letter
ALLSPHINXOPTS   = -d $(BUILDDIR)/doctrees $(PAPEROPT_$(PAPER)) $(SPHINXOPTS)
ALLSPHINXOPTS   += -W --keep-going
I18NSPHINXOPTS  = $(PAPEROPT_$(PAPER)) $(SPHINXOPTS)

.PHONY: help
help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  html       to make standalone HTML files"
	@echo "  dirhtml    to make HTML files named index.html in directories"
	@echo "  singlehtml to make a single large HTML file"
	@echo "  pickle     to make pickle files"
	@echo "  json       to make JSON files"
	@echo "  htmlhelp   to make HTML files and a HTML help project"
	@echo "  qthelp     to make HTML files and a qthelp project"
	@echo "  devhelp    to make HTML files and a devhelp project"
	@echo "  epub       to make an epub file"
	@echo "  latex      to make LaTeX files, you can set PAPER=a4 or PAPER=letter"
	@echo "  latexpdf   to make LaTeX files and run them through pdflatex"
	@echo "  latexpdfja to make LaTeX files and run them through japanese-pdflatex"
	@echo "  text       to make text files"
	@echo "  man        to make man files"
	@echo "  texinfo    to make Texinfo files"
	@echo "  info       to make Texinfo files and run them to generate info files"
	@echo "  gettext    to make PO message catalogs"
	@echo "  changes    to make an overview of all changed/added/deprecated items"
	@echo "  xml        to make Docutils-native XML files"
	@echo "  pseudoxml  to make pseudoxml-format XML files for display purposes"
	@echo "  linkcheck  to make a linkcheck report, check links for integrity"
	@echo "  doctest    to make all doctests in the source code"
	@echo "  coverage   to make a coverage report for the source code"
	@echo "  dummy      to make dummy files"
	@echo ""
	@echo "Build finished; two or more of the following print messages:"

.PHONY: clean
clean:
	rm -rf $(BUILDDIR)/*

.PHONY: html
html:
	$(SPHINXBUILD) -b html $(ALLSPHINXOPTS) . $(BUILDDIR)/html
	@echo
	@echo "Build finished. The HTML files are in $(BUILDDIR)/html."

.PHONY: dirhtml
dirhtml:
	$(SPHINXBUILD) -b dirhtml $(ALLSPHINXOPTS) . $(BUILDDIR)/dirhtml
	@echo
	@echo "Build finished. The HTML files are in $(BUILDDIR)/dirhtml."

.PHONY: singlehtml
singlehtml:
	$(SPHINXBUILD) -b singlehtml $(ALLSPHINXOPTS) . $(BUILDDIR)/singlehtml
	@echo
	@echo "Build finished. The HTML files in $(BUILDDIR)/singlehtml."

.PHONY: pickle
pickle:
	$(SPHINXBUILD) -b pickle $(ALLSPHINXOPTS) . $(BUILDDIR)/pickle
	@echo
	@echo "Pickle files in $(BUILDDIR)/pickle."

.PHONY: json
json:
	$(SPHINXBUILD) -b json $(ALLSPHINXOPTS) . $(BUILDDIR)/json
	@echo
	@echo "JSON files in $(BUILDDIR)/json."

.PHONY: htmlhelp
htmlhelp:
	$(SPHINXBUILD) -b htmlhelp $(ALLSPHINXOPTS) . $(BUILDDIR)/htmlhelp
	@echo
	@echo "HTML help files in $(BUILDDIR)/htmlhelp."

.PHONY: qthelp
qthelp:
	$(SPHINXBUILD) -b qthelp $(ALLSPHINXOPTS) . $(BUILDDIR)/qthelp
	@echo
	@echo "QtHelp files in $(BUILDDIR)/qthelp."

.PHONY: devhelp
devhelp:
	$(SPHINXBUILD) -b devhelp $(ALLSPHINXOPTS) . $(BUILDDIR)/devhelp
	@echo
	@echo "Devhelp files in $(BUILDDIR)/devhelp."

.PHONY: epub
epub:
	$(SPHINXBUILD) -b epub $(ALLSPHINXOPTS) . $(BUILDDIR)/epub
	@echo
	@echo "Epub file in $(BUILDDIR)/epub."

.PHONY: latex
latex:
	$(SPHINXBUILD) -b latex $(ALLSPHINXOPTS) . $(BUILDDIR)/latex
	@echo
	@echo "LaTeX files in $(BUILDDIR)/latex."

.PHONY: latexpdf
latexpdf:
	$(SPHINXBUILD) -b latex $(ALLSPHINXOPTS) . $(BUILDDIR)/latex
	@echo "Running LaTeX files through pdflatex..."
	$(MAKE) -C $(BUILDDIR)/latex all-pdf
	@echo "pdflatex finished; the PDF files are in $(BUILDDIR)/latex."

.PHONY: latexpdfja
latexpdfja:
	$(SPHINXBUILD) -b latex $(ALLSPHINXOPTS) . $(BUILDDIR)/latex
	@echo "Running LaTeX files through japanese-pdflatex..."
	$(MAKE) -C $(BUILDDIR)/latex all-pdf-ja
	@echo "pdflatex finished; the PDF files are in $(BUILDDIR)/latex."

.PHONY: text
text:
	$(SPHINXBUILD) -b text $(ALLSPHINXOPTS) . $(BUILDDIR)/text
	@echo
	@echo "Text files in $(BUILDDIR)/text."

.PHONY: man
man:
	$(SPHINXBUILD) -b man $(ALLSPHINXOPTS) . $(BUILDDIR)/man
	@echo
	@echo "Man files in $(BUILDDIR)/man."

.PHONY: texinfo
texinfo:
	$(SPHINXBUILD) -b texinfo $(ALLSPHINXOPTS) . $(BUILDDIR)/texinfo
	@echo
	@echo "Texinfo files in $(BUILDDIR)/texinfo."

.PHONY: info
info:
	$(SPHINXBUILD) -b texinfo $(ALLSPHINXOPTS) . $(BUILDDIR)/texinfo
	$(MAKE) -C $(BUILDDIR)/texinfo info
	@echo
	@echo "Info files in $(BUILDDIR)/texinfo."

.PHONY: gettext
gettext:
	$(SPHINXBUILD) -b gettext $(ALLSPHINXOPTS) . $(BUILDDIR)/locale
	@echo
	@echo "Pot files in $(BUILDDIR)/locale."

.PHONY: changes
changes:
	$(SPHINXBUILD) -b changes $(ALLSPHINXOPTS) . $(BUILDDIR)/changes
	@echo
	@echo "The overview file is in $(BUILDDIR)/changes."

.PHONY: linkcheck
linkcheck:
	$(SPHINXBUILD) -b linkcheck $(ALLSPHINXOPTS) . $(BUILDDIR)/linkcheck
	@echo
	@echo "Link check complete; look for any errors in the $(BUILDDIR)/linkcheck/ index.html."

.PHONY: doctest
doctest:
	$(SPHINXBUILD) -b doctest $(ALLSPHINXOPTS) . $(BUILDDIR)/doctest
	@echo
	@echo "Testing of doctests in the source files finished, check output in $(BUILDDIR)/doctest/index.html."

.PHONY: coverage
coverage:
	$(SPHINXBUILD) -b coverage $(ALLSPHINXOPTS) . $(BUILDDIR)/coverage
	@echo
	@echo "Testing of coverage in the source files finished, look at the results in $(BUILDDIR)/coverage/index.html."

.PHONY: dummy
dummy:
	$(SPHINXBUILD) -b dummy $(ALLSPHINXOPTS) . $(BUILDDIR)/dummy
	@echo
	@echo "Build finished. The HTML files are in $(BUILDDIR)/dummy."
