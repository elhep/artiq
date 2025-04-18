#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# ARTIQ documentation build configuration file, created by
# sphinx-quickstart on Thu Sep 18 16:51:53 2014.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import sys
import os
from unittest.mock import Mock

import sphinx_rtd_theme


# Ensure that ARTIQ-Python types are correctly printed
# See: https://github.com/m-labs/artiq/issues/741
import builtins
builtins.__in_sphinx__ = True


# we cannot use autodoc_mock_imports (does not help with argparse)
mock_modules = ["artiq.gui.waitingspinnerwidget",
                "artiq.gui.flowlayout",
                "artiq.gui.models",
                "artiq.compiler.module",
                "artiq.compiler.embedding",
                "artiq.dashboard.waveform",
                "artiq.coredevice.jsondesc",
                "qasync", "lmdb", "dateutil.parser", "prettytable", "PyQt6",
                "h5py", "llvmlite", "pythonparser", "tqdm", "jsonschema", "platformdirs"]

for module in mock_modules:
    sys.modules[module] = Mock()

# https://stackoverflow.com/questions/29992444/sphinx-autodoc-skips-classes-inherited-from-mock
class MockApplets:
    class AppletsDock:
        pass

sys.modules["artiq.gui.applets"] = MockApplets


# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.insert(0, os.path.abspath('../..'))

from artiq import __version__ as artiq_version

# -- General configuration ------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.mathjax',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinxarg.ext',
    'sphinxcontrib.wavedrom',  # see also below for config
    'sphinxcontrib.jquery',
    'sphinxcontrib.tikz' # see also below for config
]

mathjax_path = "https://m-labs.hk/MathJax/MathJax.js?config=TeX-AMS-MML_HTMLorMML.js"

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'ARTIQ'
copyright = '2014-2025, M-Labs Limited'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = artiq_version.split('+', 1)[0]
# The full version, including alpha/beta/rc tags.
release = artiq_version

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
#today_fmt = '%B %d, %Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build']

# The reST default role (used for this markup: `text`) to use for all
# documents.
#default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
#add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
#add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
#modindex_common_prefix = []

# If true, keep warnings as "system message" paragraphs in the built documents.
#keep_warnings = False

# If true, Sphinx will warn about *all* references where the target cannot be found.
nitpicky = True

# (type, target) regex tuples to ignore when generating warnings in 'nitpicky' mode
# i.e. objects that are not documented in this manual and do not need to be
nitpick_ignore_regex = [
    (r'py:.*', r'numpy..*'),
    (r'py:.*', r'sipyco..*'),
    ('py:const', r'.*'), # no constants are documented anyway
    ('py.attr', r'.*'), # nor attributes
    (r'py:.*', r'artiq.gateware.*'),
    ('py:mod', r'artiq.test.*'),
    ('py:mod', r'artiq.applets.*'),
    # we can't use artiq.master.* because we shouldn't ignore the scheduler
    ('py:class', r'artiq.master.experiments.*'),
    ('py:class', r'artiq.master.databases.*'),
    ('py:.*', r'artiq.master.worker.*'),
    ('py:class', 'dac34H84'),
    ('py:class', 'trf372017'),
    ('py:class', r'list(.*)'),
    ('py.class', 'NoneType'),
    ('py:meth', 'pause')
]

# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'sphinx_rtd_theme'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {}

# Add any paths that contain custom themes here, relative to this directory.
#html_theme_path = []

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
#html_title = None

# A shorter title for the navigation bar.  Default is the same as html_title.
#html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
html_logo = '../logo/artiq_white.png'

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
#html_favicon = None

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Add any extra paths that contain custom files (such as robots.txt or
# .htaccess) here, relative to this directory. These files are copied
# directly to the root of the documentation.
#html_extra_path = []

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
#html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
#html_additional_pages = {}

# If false, no module index is generated.
#html_domain_indices = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
#html_split_index = False

# If true, links to the reST sources are added to the pages.
#html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
#html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
#html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = None

# Output file base name for HTML help builder.
htmlhelp_basename = 'ARTIQdoc'


# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
# The paper size ('letterpaper' or 'a4paper').
#'papersize': 'letterpaper',

# The font size ('10pt', '11pt' or '12pt').
#'pointsize': '10pt',

# Additional stuff for the LaTeX preamble.
#'preamble': '',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
  ('index', 'ARTIQ.tex', 'ARTIQ Documentation',
   'M-Labs and contributors', 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
#latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = False

# If true, show page references after internal links.
#latex_show_pagerefs = False

# If true, show URL addresses after external links.
#latex_show_urls = False

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_domain_indices = True


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'artiq', 'ARTIQ Documentation',
     ['M-Labs and contributors'], 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
  ('index', 'ARTIQ', 'ARTIQ Documentation',
   'M-Labs and contributors', 'ARTIQ', 'A leading-edge control system for quantum information experiments.',
   'Miscellaneous'),
]

# Documents to append as an appendix to all manuals.
#texinfo_appendices = []

# If false, no module index is generated.
#texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#texinfo_show_urls = 'footnote'

# If true, do not generate a @detailmenu in the "Top" node's menu.
#texinfo_no_detailmenu = False

# -- Options for sphinxcontrib-wavedrom -----------------------------------
offline_skin_js_path = '_static/default.js'
offline_wavedrom_js_path = '_static/WaveDrom.js'
render_using_wavedrompy = True

# -- Options for sphinxcontrib-tikz ---------------------------------------
# tikz_proc_suite = pdf2svg
# tikz_transparent = True
# these are the defaults

tikz_tikzlibraries = 'positioning, shapes, arrows.meta'