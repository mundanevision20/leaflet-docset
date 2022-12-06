
import html
import logging
import os
from pathlib import Path
from pprint import pprint
import json
import re
import shutil
import sys
import zipfile

from bs4 import BeautifulSoup, Comment
import css_parser
import htmlmin
import requests

from pygments import highlight
from pygments.lexers import guess_lexer, get_lexer_by_name
from pygments.formatters import HtmlFormatter

logging.basicConfig(level=logging.DEBUG)

css_parser.log.setLevel(logging.INFO)

docs_dir = Path("dist/leaflet.docset/Contents/Resources/Documents")

# os.system(f"wget --convert-links --page-requisites --directory-prefix={docs_dir.absolute()} https://leafletjs.com/reference.html")

leaflet_dir = docs_dir / "leafletjs.com"

static_dir = leaflet_dir / "docs"

# popup dialog
dialog_path = leaflet_dir / "dialog"
if dialog_path.exists():
    shutil.rmtree(dialog_path)

# highlight.js -> replaced by pygments static rendering below
hljs_path = static_dir / "highlight"
if hljs_path.exists():
    shutil.rmtree(hljs_path)

index_path = leaflet_dir / "reference.html"

if not index_path.exists():
    logging.error(
        f"while trying to access '{index_path}' -> 'exists' is '{index_path.exists()}' ")
    sys.exit(1)

index_size = index_path.stat().st_size

if index_size < 2:
    logging.error(
        f"while trying to read contents of '{index_path}' -> 'size' is '{index_size} bytes' ")
    sys.exit(1)

logging.debug(f"size of '{index_path}' is '{index_size} bytes' ")

index_html = ''

logging.debug(f"reading from '{index_path}' ... ")

index_old_size = index_path.stat().st_size

with open(index_path, 'r', encoding='utf-8') as fh:
    index_html = str(fh.read())

index_len = len(index_html)

logging.debug(f"reading from '{index_path}' (length: {index_len}) completed ")

# breaks <code> contents
# index_html = html.unescape(str(index_html))

# fix anchors
index_html = str(re.sub(r'(href=)([\"\'])(reference\.html)(\#[^\"\']+)([\"\'])',r'href="\g<4>"', str(index_html)))

# highlight hex color strings
# index_html = str(re.sub(r'(<code>)([\'\"])(\#[\w]{6})([\'\"])(</code>)',r'<code data-color="\g<3>">\g<2>\g<3>\g<4></code>', str(index_html)))

docset_soup = BeautifulSoup(index_html, features='html.parser')

logging.debug(f"removing surplus contents ...")

tag_groups = [docset_soup.select('nav.ext-links'), docset_soup.select('link[rel="alternate"]'), docset_soup.select('link[rel$="icon"]'), docset_soup.select('body > header'), docset_soup.select(
    'body > nav'), docset_soup.select('#toc'), docset_soup.select('script'), docset_soup.select('link[href^="http"]'), docset_soup.select('link[href^="docs/highlight"]')]

for tag_selector in tag_groups:
    for tag in tag_selector:
        tag.decompose()

for tag in docset_soup.select('script'):
    tag_src = str(tag.get('src')).replace('None','').strip()
    if len(tag_src) == 0:
        tag_str = str(tag)
        if len(tag_str) > 50:
            tag_str = tag_str[0:49] + '...'
        tag_str = re.sub(r'(?im)[\r\n\t]+',' ',tag_str)
        logging.debug(f"removing inline js '{tag_str}' ")
        tag.decompose()

code_tags = docset_soup.select('pre > code')
len_code_tags = len(code_tags)
for tag_index in range(len_code_tags):
    tag = code_tags[tag_index]
    if len(list(tag.select('*'))) == 0:
        lang_attr = ''
        tag_class = tag.get('class')
        if tag_class != None:
            lang_class = str(tag_class[0]).lower().replace('none','')
            lang_attr = lang_class.replace('language-','')
        tag_str = str(tag.string)
        logging.debug(f"({tag_index+1}/{len_code_tags}) preparing syntax highlighting ...")
        
        lexer = None
        if len(lang_attr) > 0:
            try:
                lexer = get_lexer_by_name(lang_attr)
            except Exception as e:
                logging.error(f"failed to get pygments lexer for highlight.js attribute '{lang_attr}' -> error: {e} ")
        else:
            lexer = guess_lexer(tag_str, stripall=True)
        
        if lexer == None:
            lexer = get_lexer_by_name('plaintext')

        highlight_class = "highlight-"+str(tag_index+1)
        formatter = HtmlFormatter(linenos=False, cssclass=highlight_class, cssstyles='background:transparent;', prestyles='background:transparent;white-space:pre-wrap;overflow:hidden;', nobackground=True, lineseparator="<br>", linespans=highlight_class)
        result = highlight(tag_str, lexer, formatter)
        highlight_class = '.'+highlight_class
        tag.replace_with(BeautifulSoup(result, features="html.parser").select(highlight_class)[0])

        pre_css_str = str(formatter.get_style_defs(highlight_class))
        pre_css_str = re.sub(r'(?m)(\/\*)([^*]+)(\*\/)', '', str(pre_css_str)) # remove css comments
        pre_css_str = re.sub(r'(?m)[\t\n\r]+', '', str(pre_css_str)) # remove tabs and line breaks

        pre_css = f"<style>{pre_css_str}</style>"

        pre_css_tag = BeautifulSoup(pre_css, features="html.parser").select('style')[0]
        docset_soup.select(highlight_class)[0].append(pre_css_tag)
        logging.debug(f"({tag_index+1}/{len_code_tags}) syntax highlighting done")

docset_soup.body.append(BeautifulSoup(f"<script src=\"docs/js/reference.js\"></script>", features="html.parser").select('script')[0])

css_links = docset_soup.select('link[rel="stylesheet"]')
css_styles = ''
import_pattern = re.compile(r'(?m)(\@import url\(\")([^\"]+)(\"\)\;)')

for css_link in css_links:
    link_href = str(css_link.get('href'))
    link_path = leaflet_dir / Path(link_href)
    logging.debug(f"validating existance of '{link_path}' ... ")
    if not link_path.exists():
        logging.debug(f"removing '{css_link}' -> source file does not seem to exist")
        css_link.decompose()
    else:
        logging.debug(f"found '{link_path}' (size: {link_path.stat().st_size}) ")

        logging.debug(f"reading from '{link_path}' ... ")

        css_rules = ''
        with open(link_path, 'r', encoding='utf-8') as fh:
            css_rules = '\n' + str(fh.read())

        logging.debug(f"reading from '{link_path}' (length: {link_path.stat().st_size}) completed ")

        css_imports = list(re.findall(import_pattern, css_rules))
        if len(css_imports) > 0:
            for css_import in css_imports:
                import_path = static_dir / Path(str(css_import[1]))
                if import_path.exists():
                    logging.debug(f"reading from '{import_path}' ... ")

                    with open(import_path, 'r', encoding='utf-8') as fh:
                        css_rules = '\n' + str(fh.read()) + '\n' + css_rules

                    logging.debug(f"reading from '{import_path}' (length: {import_path.stat().st_size}) completed ")
                else:
                    logging.debug(f"reading from '{import_path}' failed -> file does not seem to exist ")

        css_styles += css_rules

for style_tag in docset_soup.select('style'):
    css_styles += '\n'+str(style_tag.text).strip()
    style_tag.decompose()

css_min_file = "styles.min.css"
css_min_path = static_dir / "css" / css_min_file
last_link = docset_soup.select('link[rel="stylesheet"]')[-1]
last_link['href'] = 'docs/css/' + css_min_file
last_link['type'] = 'text/css'
del last_link['media']

css_links = docset_soup.select('link[rel="stylesheet"]')
for link_index in range(len(css_links)-1): # remove all other 'link' tags
    css_links[link_index].decompose()

css_styles = re.sub(import_pattern,'',css_styles) # remove obsolete imports -> after merging all files

styles_parser = css_parser.CSSParser(raiseExceptions=False)
css_sheet = styles_parser.parseString(css_styles)

found_rules = []
remove_rules = []
removed_counter = 0
for css_rule in css_sheet:
    try:
        if hasattr(css_rule, 'media'):
            remove_rules2 = []
            for css_rule2 in css_rule:
                css_select = str(css_rule2.selectorText)
                if ':before' not in css_select and ':after' not in css_select: # both are not implemented -> see https://github.com/facelessuser/soupsieve/issues/198
                    tag_matches = docset_soup.select(css_select)
                    if len(tag_matches) == 0 and 'expanded' not in css_select:
                        #print(css_select)
                        remove_rules2.append(css_rule2)

            for css_rule2 in remove_rules2:
                css_rule.cssRules.remove(css_rule2)
                removed_counter += 1

            continue
        elif hasattr(css_rule, 'selectorText'):
            css_select = str(css_rule.selectorText)
            # ':before' and ':after' are not implemented -> see https://github.com/facelessuser/soupsieve/issues/198
            # we'll also skip pygment highlight css as it's already optimized
            if css_select not in css_select and ':before' not in css_select and ':after' not in css_select and '.highlight-' not in css_select:
                print(css_select)
                tag_matches = docset_soup.select(css_select)
                if len(tag_matches) == 0 and 'expanded' not in css_select:
                    #print(css_select)
                    remove_rules.append(css_rule)
            elif css_select not in found_rules:
                found_rules.append(css_select)
        else:
            #print(css_rule)
            remove_rules.append(css_rule)
    except Exception as e:
        logging.error(f"processing of css rule '{css_rule}' failed -> error: {e}")

for css_rule in remove_rules:
    css_sheet.cssRules.remove(css_rule)

logging.debug(f"removed {removed_counter + len(remove_rules)} obsolete css rules")

old_css_len = len(css_styles)
css_styles = str(css_sheet.cssText.decode())

css_styles = str(re.sub(r'(?m)[\n\r]+', '', css_styles))
css_styles = str(re.sub(r'(?m)( ){2}', '', css_styles))

new_css_len = len(css_styles)

css_files = list(static_dir.glob('*.css'))

logging.debug(f"found {len(css_files)} obsolete css files")
#pprint(js_files)
for css_file in css_files:
    logging.debug(f"deleting '{css_file}' ... ")
    # try:
    #     css_file.unlink()
    # except Exception as e:
    #     logging.error(f"failed to delete '{css_file}' -> error: {e}")

css_len_diff = old_css_len - new_css_len
css_len_percent = css_len_diff / old_css_len * 100
logging.debug(f"reduced size of css by {css_len_diff} characters (to ca. {round(css_len_percent, 1)} percent of original) ")

custom_styles = """
a {
    text-decoration: none;
    transition: 1s ease all;
}
a:hover {
    text-decoration: underline;
}

div.accordion.expanded label, section>h4 {
    top: 0em;
}

@media screen and (prefers-color-scheme: dark) {
    *,
    h1, h2, h3, h4,
    table th, table td,
    p {
        color: rgb(224, 211, 211);
        background-color: rgb(31, 31, 37);
    }
    a {
        color: #7abf6d;
    }
    .api-page table td code b,
    .api-page table td:last-child {
        color: rgb(224, 211, 211);
        background: transparent;
    }
    .api-page table td code i {
        color: #a6d9a6;
    }

    div.accordion.expanded label, section>h4 {
        background: rgb(31, 31, 37);
    }

    .api-page h2[id]:hover:before,
    .api-page tr[id]:hover td:first-child:before {
        filter: invert(1);
    }

    tr:target, tr:target td:nth-of-type(1) {
        background: transparent;
        border-color: #cf8414!important;
    }
}

@media print {
    *,
    h1, h2, h3, h4,
    table th, table td,
    p {
        color: rgb(0, 0, 0);
        background-color: transparent;
    }
    a, a:visited, :active, a:focus, a:hover {
        color: #000000;
        text-decoration: underline;
    }
    a[href]::after {
        content: " ("attr(href)")";
        color: rgb(0, 0, 0);
        background-color: transparent;
        font-style: italic;
        size: 95%;
    }
    tr:target, tr:target td:nth-of-type(1) {
        background: transparent;
        border-color: none!important;
    }
}
"""
css_styles += custom_styles

css_styles = re.sub(r'(?m)(\/\*)([^*]+)(\*\/)', '', str(css_styles)) # remove css comments
css_styles = re.sub(r'(?im)[\r\n]+', '', str(css_styles)) # remove line breaks
css_styles = re.sub(r'(?im)( )( )+', ' ', str(css_styles)) # surplus spaces

with open(css_min_path, 'w+', encoding='utf-8') as fh:
    fh.write(css_styles)

for tag in docset_soup.body.children:
    if isinstance(tag, Comment): # remove html comments
        tag.decompose()

nodes_list = []
for table_tag in docset_soup.select('section table'):
    type_str = table_tag.select('thead > tr > th:first-of-type')
    if len(type_str) == 1:
        type_str = html.unescape(re.sub(r'(?im)<[^>]+>','',str(type_str[0])))
        print(f"type -> {type_str}")
        for node_tag in table_tag.select('tbody > tr > td:first-of-type'):
            node_str = html.unescape(re.sub(r'(?im)<[^>]+>','',str(node_tag)))
            nodes_list.append({
                'type':type_str,
                'name':node_str
            })
            print(f"     node -> {str(node_str)}")

with open("nodes.json", 'w+', encoding='utf-8') as fh:
    fh.write(str(json.dumps(nodes_list)))

docset_soup = str(docset_soup)

js_path = static_dir / "js"
js_files = list(js_path.glob('*.js'))

logging.debug(f"found {len(js_files)} javascript files")
#pprint(js_files)
for js_file in js_files:
    js_fn = str(js_file.stem+js_file.suffix)
    if js_fn not in docset_soup:
        logging.debug(f"deleting '{js_file}' ... ")
        # try:
        #     js_file.unlink()
        # except Exception as e:
        #     logging.error(f"failed to delete '{js_file}' -> error: {e}")

img_path = static_dir / "images"
img_files = list(img_path.glob('*.*'))

logging.debug(f"found {len(img_files)} image files")
pprint(img_files)
for img_file in img_files:
    img_fn = str(img_file.stem+img_file.suffix)
    if img_fn not in docset_soup and img_fn not in css_styles:
        logging.debug(f"deleting '{img_file}' ... ")
        # try:
        #     img_file.unlink()
        # except Exception as e:
        #     logging.error(f"failed to delete '{img_file}' -> error: {e}")

index_len = len(index_html)

logging.debug(f"removed surplus contents -> new length: {index_len} ")

ref_path = leaflet_dir / "index.html"
with open(ref_path, 'w+', encoding='utf-8') as fh:
    fh.write(str(docset_soup))
