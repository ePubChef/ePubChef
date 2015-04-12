'''
ePubChef - generating EPUB files for eBooks
    Copyright (C) 2015  John Cobo
    info@epubchef.org

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''
# generate (or "cook") an eBook from text files.
# If the book is to be called "demo", the text files should be in folder "demo_raw"
# and include "demo_recipe.txt" which contains necessary meta-data.
# Run with: python cook.py demo  # if your book is called 'demo'.
# Optional second arguments are "debug", or "validate", or "kindlegen" eg. python cook.py demo validate

# debug populates a /debug directory, validate runs EPUB check if it has been set up (Java, etc.)
# Output generated to the directory "demo_cooked" and the epub (and .mobi) to "demo_served".

import pystache
import os
import sys
from os.path import isfile, join
import glob
import shutil
import pprint
import codecs
import yaml
import re
import json
import zipfile
import subprocess
import markdown
import datetime

cook_dir = os.path.dirname(os.path.realpath(__file__))

# not using python logging module to reduce external dependencies
log = open(join(cook_dir, "cook_log.txt"), 'w')
log.write("****starting to cook***** at " + str(datetime.datetime.now()) + " (Ireland time)\r\n")

def msg(msg_txt):
    print(msg_txt)
    log.write("\r\n" + msg_txt)

template_dir = "templates"

# get the recipe file for the book
file_name = sys.argv[1]
gen_dir = os.path.join(cook_dir, file_name+'_cooked')

# check for a debug level and validate run
arg2 = None
try:
    arg2 = sys.argv[2]
except:
    pass

msg('cook_dir: '+ cook_dir)

dirs = {
    'gen_dir' : gen_dir, # folder for the ePub files
    'template_dir' : os.path.join(cook_dir, 'templates'),         # templates for ePub files
    'raw_book' : os.path.join(cook_dir, file_name+'_raw'), # words and images of the book
    'oebps' : os.path.join(cook_dir, gen_dir+'/OEBPS'),
    'raw_images' : os.path.join(cook_dir, file_name+'_raw'+'/images'),
    'images' : os.path.join(cook_dir, gen_dir+'/OEBPS/images'),
    'default_cover' : os.path.join(cook_dir, 'demo_raw/images'),
    'content' : os.path.join(cook_dir, gen_dir+'/OEBPS/content'),
    'css' : os.path.join(cook_dir, 'css'),
    'tmp' : os.path.join(cook_dir, 'debug'),
    'epub_loc' : os.path.join(cook_dir, file_name+'_served'),
    'fonts' : os.path.join(cook_dir, 'fonts'),
    'fonts_gen' : os.path.join(cook_dir, gen_dir+'/OEBPS/fonts'),
    'demo_raw' : os.path.join(cook_dir, 'demo_raw'),
    'recipe_loc' : os.path.join(cook_dir, file_name+'_raw', file_name+'_recipe.txt'),
    'raw_css' : os.path.join(cook_dir, file_name+'_raw', 'css'),
	}


''' structure to be generated for "mybook" is:
  /mybook_generated (generated book root dir)
      mimetype
  mybook_generated/META-INF
     container.xml
  mybook_generated/OEBPS
     content.opf
     cover.xhtml
     toc.ncx
  mybook_generated/OEBPS/content
     content001.xhtml
     content...xhtml
     xhtmloc.xhtml
  mybook_generated/OEBPS/css
     epub-stylesheet.css
  mybook_generated/OEBPS/images
     cover_image.jpg
     ... images
  mybook_generated/OEBPS/fonts
     ... fonts
'''

''' source files are:
  / ( eBookChef root)
     cook.py
  /css
     epub-stylesheet.css
  /mybook_raw
     mybook_recipe.txt
     _0010_010_scene....txt (many scene files)
  /mybook_raw/images
     ...jpg *
  /mybook_raw/fonts
     ...,odt, woff
  /templates
     content.mustache
     table_of_contents.mustache
     title.mustache
     ....(more)


'''

'''
textblocks and paras are created by templates/scene.mustache
A textblock is a Python dictionary containing a list of word dictionaries.
Each item in the list contains "words" and optionally a "text_class." For example:
"textblock": [ {"text_class": "bold",
                "words": "This is bold."},
	       {"words": "This has no class"}
	     ]

paragraphs are items in a dictionary called "paras". Each item is either a "textblock"
of which there can be many, or a "class" which defines the xhtml class of the paragraph.
'''
renderer = pystache.Renderer()

def importYaml(file_name):
    recipe_loc = dirs['recipe_loc']
    if os.path.isfile(recipe_loc):
        msg('Opening recipe for: '+ recipe_loc)
        try:
            with open(recipe_loc, 'r') as f:
                _recipe = yaml.load(f)
        except:
            msg('\n***Error in recipe file, please check your yaml*** : '+ recipe_loc)
            msg('***Try checking it with http://yaml-online-parser.appspot.com***')
            msg('***Escape characters such as colons by adding quotes around the text.***\n')
            raise SystemExit
    else: # create a new recipe from a template
        msg('NO RECIPE FOUND AT: '+ recipe_loc)
        msg('Creating new recipe for: '+ file_name)
        try:
            f = open(join(dirs['raw_book'], file_name+'_recipe.txt'), 'w')
        except:   # create the dir if it did not exist
            os.makedirs(dirs['raw_book'])
            f = open(join(dirs['raw_book'], file_name+'_recipe.txt'), 'w')

        new_recipe = renderer.render_path(os.path.join(dirs['template_dir'], 'recipe.mustache'), dict([("file_name", file_name)]))

        f.write(new_recipe)
        f.close()
        with open(join(dirs['raw_book'], file_name+'_recipe.txt'), 'r') as f:
            _recipe = yaml.load(f)

    # augment recipe by adding the file name to it
    _recipe['file_name'] = file_name
    return _recipe

def createEmptyDir(dir_nm, add_init):
    # create a directory if it does not exist, delete files
    # from it if it already existed.
    # Optionally add an empty __init__.py to the dir.
    if not os.path.exists(dir_nm): # create it if it does not exist
        os.makedirs(dir_nm)
    else:
        # delete contents if it already existed
        msg('deleting previously generated contents of directory: '+  dir_nm)
        shutil.rmtree(dir_nm)
        try:
            os.makedirs(dir_nm)
        except:
            pass # already exists
    if add_init:
        f = open(os.path.join(dir_nm, '__init__.py'),'w+')
        f.close()

def prepareDirs(dirs):
    # delete previous generated folders
    if arg2 == 'debug':
        msg('RUNNING in DEBUG mode, see folder: /'+ dirs['tmp'])
        #os.makedirs(dirs['tmp'])
        f = open(os.path.join(dirs['tmp'], 'tmp_paras.json'), 'w')
        f.close()
        f = open(os.path.join(dirs['tmp'],'tmp_all_paras.json'), 'w')
        f.close()

    # top level generated book dir
    createEmptyDir(dirs['gen_dir'],False)

    # main content
    content_dir = dirs['content']
    createEmptyDir(content_dir,False)

    # images including cover image
    try:
        shutil.copytree(dirs['raw_images'], dirs['images'])
    except: # create ..._raw and ..._raw/images if they don't exist
        os.makedirs(dirs['raw_images'])
        src = os.path.join(dirs['demo_raw'], 'images', 'cover_image.jpg')
        #src = 'demo_raw/images/cover_image.jpg'
        shutil.copyfile(src, dirs['raw_images']+'/cover_image.jpg')

        # try again now that chapters and cover image has been created
        shutil.copytree(dirs['raw_images'], dirs['images'])

	# ePubChef creation image
    src = os.path.join(dirs['template_dir'], 'epubchef_logo.jpg')
    dst = os.path.join(dirs['oebps'],'images', 'epubchef_logo.jpg')
    shutil.copyfile(src, dst)

    # fonts
    shutil.copytree(dirs['fonts'], dirs['fonts_gen'])
    # try:
        # shutil.copytree(dirs['fonts'], dirs['fonts_gen'])
    # except: # create ..._raw and ..._raw/fonts if they don't exist
    #    os.makedirs(dirs['raw_fonts'])
        # src = os.path.join(dirs['demo_raw'], 'fonts')
        # shutil.copytree(src, dirs['raw_fonts'])
      #  try again
        # shutil.copytree(dirs['raw_fonts'], dirs['fonts'])

    # css
    css_dst = os.path.join(dirs['oebps'],'css')
    shutil.copytree(dirs['css'], css_dst)

    # TODO fix permission error here
    #dst = os.path.join(dirs['oebps'],'css')
    #src = dirs['raw_css']
    #for item in os.listdir(src):
    #    shutil.copyfile(src, dst)

	# mimetype
    src = os.path.join(dirs['template_dir'], 'mimetype')
    dst = os.path.join(dirs['gen_dir'], 'mimetype')
    shutil.copyfile(src, dst)

	# META-INF
    os.makedirs(os.path.join(dirs['gen_dir'], 'META-INF'))
    src = os.path.join(dirs['template_dir'], 'container.xml')
    dst = os.path.join(dirs['gen_dir'], 'META-INF', 'container.xml')
    shutil.copyfile(src, dst)

def removeBlankLines(input):
    # TODO improve this hack to git rid of blank lines
    non_blank_lines = []
    for line in input:
        if len(line) > 0:
            non_blank_lines.append(line)
    return non_blank_lines

def processMarkdown(_line):
    # markdown headers - add an extra level as the chapter header is <h1>

    if _line[0] == "#":
        _line = "#"+_line

    if _line[0] == "|":
        msg("got a table: "+_line)
    _line = markdown.markdown(_line, output_format='xhtml5')
    return _line

def groupMarkdown(_n, lines):
    # some markdown such as lists and tables use more than one line from the input file. Note that the counter n will be adjusted by this function.
    # Simple lists
    list_init = ["* ", "1.", "2.", "3.", "4.", "5." \
               , "6.", "7.", "8.", "9."]
    line = lines[_n]
    if line[0:2] in list_init:  # markdown list
        m = _n+1
        try:
            while lines[m][0:2] in list_init:
                line = line + "\n" + lines[m]
                _n+=1
                m+=1
        except:
            pass # end of list

    # # Even though this code does what I think it should, markdown is not
    # # creating a table from the output. TODO: investigate further.
    # table_init = ["|"]
    # line = lines[_n]
    # if line[0] in table_init:  # markdown table
        # #print("got a table:", line)
        # m = _n+1
        # try:
            # while lines[m][0] in table_init:
                # #print("is it a table:", line)
                # line = line + "\n" + lines[m]
                # _n+=1
                # m+=1
        # except:
            # pass # end of table
        # #print("whole table:", line)
    return _n, line

def formatScene(in_file, scene_count, auto_dropcaps):
    # replace characters we don't like
    lines = [line.strip() for line in in_file]

    style = next_para_style = None
    all_paras = {}
    paras = []
    non_blank_lines = removeBlankLines(lines)

    need_to_clear = False
    para_count = 0
    n = 0
    while n < len(non_blank_lines):
        line = non_blank_lines[n]
        para_class = setParaClass(para_count, scene_count=0)
        para = {}
        textblock = []
        text_class = False # default

        line = preMarkdownTextClean(line)

        # process any markdown in the text
        n, line = groupMarkdown(n, non_blank_lines)
        line = processMarkdown(line)

        line = postMarkdownTextClean(line)


	    # drop capitals in the first character of a chapter
        if auto_dropcaps and scene_count == 0 and para_count == 0 and line[0] not in ['&']:

            # XXXX send all lines (paragraphs) through markdown, change
            # the <p> and add drop cap after markdown.

            if auto_dropcaps         \
               and scene_count == 0  \
               and para_count == 0   \
               and line[0:3] == "<p>" \
               and line[3] not in ['"','&']:
                char_to_drop = line[3]
                line = line[4:] # remove <p> and first chara
                new = '<p class="texttop"><span class="dropcap">' \
                       + char_to_drop + '</span>'
                line = new + line

        # text_class and words
        std_text_block = block(para, para_class, text_class, line)
        textblock.append(std_text_block)
        para_count +=1

        para['textblock'] = textblock
        paras.append(para)
        all_paras['paras'] = paras

        n+=1 # go to next line

    prepared_scene = generateJson(all_paras)

    _scene = dict(paras = paras)
    return _scene

def genPage(_recipe, page_name):
    # generate a page (non-chapter page)
    if page_name in ['table_of_contents','title_page']:
        out_dir = 'content'
    else:
        out_dir = 'oebps'

    f = codecs.open(os.path.join(dirs[out_dir], page_name+".xhtml"), 'w', 'utf-8')
    out = renderer.render_path(os.path.join(dirs['template_dir'],
	    page_name+'.xhtml'), _recipe)
    f.write(out)
    f.close()

def genPackageOpf(_recipe):
    # generate package.opf file
    f = codecs.open(os.path.join(dirs['oebps'],'package.opf'), 'w', 'utf-8')
    out = renderer.render_path(os.path.join(dirs['template_dir'], 'packageopf.xhtml'), _recipe)
    f.write(out)
    f.close()

def genTocNcx(_recipe):
    # generate toc.ncx
    f = codecs.open(os.path.join(dirs['oebps'],'toc.ncx'), 'w', 'utf-8')
    out = renderer.render_path(os.path.join(dirs['template_dir'], 'tocncx.xhtml'), _recipe)
    f.write(out)
    f.close()

def genChapters(_recipe, front_matter_count, scenes_dict):
    chapter_nbr = 0
    part_nbr = 0
    for chapter in _recipe['chapters']:
        chapter_nbr +=1
        chapter['nbr'] = str(chapter_nbr) 
        chapter['nbr_fmt'] = str("%03d" % (chapter_nbr,))
        chapter['id'] = 'h2-'+str(chapter_nbr)
        next_playorder = front_matter_count + chapter_nbr + part_nbr
        if 'starts_part' in chapter:
            _recipe['parts'][part_nbr]['playorder'] = next_playorder
            chapter['playorder'] = str(next_playorder + 1)
            part_nbr+=1
        else:
            chapter['playorder'] = str(next_playorder)

        scene_nbr = 0
        chapter = genChapter(chapter, scenes_dict[chapter['code']])

    msg("chapter count: "+ str(chapter_nbr))
    return _recipe, next_playorder

def genChapter(_chapter, scenes):
    # generate the book using templates and the recipe
    _chapter['scenes'] = []
    scene_count = 0 # counts the position of the scene in this chapter
                      # for dividers and drop_caps
    for scene_name in scenes:
        #add divider between scenes
        if scene_count > 0:
            _chapter['scenes'].append(dict(divider = True))
	# turn the raw text into structured text
        prepared_scene = prepareScene(scene_name, scene_count)
        _chapter['scenes'].append(prepared_scene)
        scene_count+=1
    # write the chapter
    f = codecs.open(os.path.join(dirs['content'], 'chap'+_chapter['nbr_fmt']+'.xhtml'), 'w', 'utf-8')
	#f = codecs.open(os.path.join(dirs['content'], 'chap'+_chapter['nbr']+'.xhtml'), 'w', 'utf-8')
    out = renderer.render_path(os.path.join(dirs['template_dir'], 'chapter.xhtml'), _chapter)
    #remove blank lines
    out =  "".join([s for s in out.strip().splitlines(True) if s.strip()])
    f.write(out)
    f.close()

    return _chapter

def preMarkdownTextClean(line):
    # escape odd characters
    line = line.replace("'","&#39;") # single quote

    return line

def postMarkdownTextClean(line):
	# three dots ... to an elipsis
    line = line.replace('...',"&#8230;")

    line = line.replace("&rsquo;","&#8217;") # right single quote
    line = line.replace("&lsquo;","&#8216;") # left single quote
    line = line.replace("&pound;","&#163;") # pound sign

    # left double quotes #########################
    # replace straight double quote following a space with left smart quote
    line = line.replace(' "'," &#8220;")

    # replace straight double quote at start of a line with a left smart quote
    if line[0:4] == '<p>"':
        line = line.replace('"',"&#8220;", 1)

    # undo smart quotes on xhtml links
    line = line.replace('<a &#8220;','<a "')

    # right double quotes #######################
    # replace straight double quote preceding a space with a right smart quote
    line = line.replace('" ',"&#8221; ")

    # replace straight double quote following a period with a right smart quote at end of paragraphs
    line = line.replace('."',".&#8221;")

    # replace straight double quote following a question mark with a right smart quote
    line = line.replace('?"',"?&#8221;")

    # replace straight double quote following a exclamation with a right smart quote
    line = line.replace('!"',"!&#8221;")

    # undo smart quotes on image xhtml links - part one
    line = line.replace('.jpg&#8221;','.jpg"')
    line = line.replace('.png&#8221;','.png"')
    # undo smart quotes on image xhtml links - part two
    line = line.replace('&#8221;/>','"/>')
    line = line.replace('&#8221; />','" />')
    # undo smart quotes on image xhtml links - part three
    line = line.replace('&#8221; alt=','" alt=')
    line = line.replace('&#8221; src=','" src=')

    # left single quotes ##########################
    # replace straight single quote following a space with left smart quote
    line = line.replace(" '"," &#8216;")

    # replace straight single quote at start of a line with a left smart quote
    if line[0:4] == "<p>'":
        line = line.replace("'","&#8216;", 1)

    # right single quotes ########################
    # replace straight single quote preceding a space with a right smart quote
    line = line.replace("' ","&#8217; ")

    # replace straight single quote following a period with a right smart quote
    line = line.replace(".'",".&#8217;")

    # ampersands
    line = re.sub(r'&(?![#a-zA-Z0-9]+?;)', "&#38;", line)
    line = line.replace(" &amp; "," &#38; ")

    # double spaces to single
    line = line.replace("  "," ")
    return line

def setParaClass(para_count, scene_count):
    para_class = False
    text_class = False
    if scene_count == 0:  # first scene in chapter
        if para_count == 0: # first paragraph
            para_class = 'texttop'
        elif para_count == 1:
            para_class = 'clearit' # clear after a drop caps
    return para_class #, text_class

def dropCap(line):
    # deal with drop capital instructions ( [__ )
    drop_letter = line[0] # return letter do be dropped
    line = line[1:] # remove first letter from rest of line
    #drop_letter = line[3] # return letter do be dropped
    #line = line[4:] # remove formatting and first letter
    text_class = 'dropcap'
    return drop_letter, line, text_class

def block(para, para_class, text_class, words):
    if para_class:
        para['class'] = para_class
    the_block = {'words' : words}
    if text_class:
        the_block['text_class'] = text_class
    return the_block

def generateJson(all_paras):
    # use a template to generate the scene in json format
    prepared_scene = renderer.render_path(os.path.join(template_dir, 'scene.mustache'), all_paras)
     # write the json file, just for humans
    if arg2 == 'debug':
        f = open(os.path.join(dirs['tmp'],'tmp_all_paras.json'), 'a')
        f.write("\n")
        json.dump(all_paras, f)
        f.close()

        f = open(os.path.join(dirs['tmp'],'tmp_paras.json'), 'a')
        f.write("\n")
        json.dump(prepared_scene, f)
        f.close()
    return prepared_scene

def prepareScene(scene_name, scene_count):
    # open raw scene file
    in_file = codecs.open(join(dirs['raw_book'], scene_name+'.txt'), 'r', 'utf-8')
    prepared_scene = formatScene(in_file, scene_count, recipe['auto_dropcaps'])
    in_file.close()
    return prepared_scene

def checkFrontBackMatter(_recipe):
    # create an empty list for front_matter if there is no list from the recipe
    if 'front_matter' not in _recipe:
        _recipe['front_matter'] = []
    if type(_recipe['front_matter']) is not list:
        _recipe['front_matter'] = []

    # create an empty list for back_matter if there is no list from the recipe
    if 'back_matter' not in _recipe:
        _recipe['back_matter'] = []
    if type(_recipe['back_matter']) is not list:
        _recipe['back_matter'] = []

    if {'name':'cover'} not in _recipe['front_matter']:
        msg('front_matter:'+ _recipe['front_matter'])
        raise Exception("You must have 'cover' in front_matter!")

    if {'name':'title_page'} not in _recipe['front_matter']:
        msg('front_matter:'+ _recipe['front_matter'])
        raise Exception("You must have 'title_page' in front_matter!")

    if {'name':'table_of_contents'} not in _recipe['front_matter']:
        msg('front_matter:'+ _recipe['front_matter'])
        raise Exception("You must have 'table_of_contents' in front_matter!")

    for fname in _recipe['front_matter'] + _recipe['back_matter'] :
        # create a dummy template if none exist
        if not os.path.isfile(join(dirs['template_dir'],fname['name']+'.xhtml')):
            src = join(dirs['template_dir'], 'template_template.xhtml')
            dst = join(dirs['template_dir'], fname['name']+'.xhtml')
            shutil.copyfile(src, dst)
    return _recipe

def addPOSData(pos_data_loc):
    # adds last second Point Of Sale data to the recipe.
    # pos_data_loc is a file system or http location of date to add to the recipe
    # it must be YAML file similar to the book recipe file. It will be appended to the recipe
    # TODO: augment to read from a URL or as input to this job
    # local file read works fine for demonstrations.
    try:
        pos_data_loc = os.path.join(file_name+'_raw', file_name+'_pos_data.txt')
        msg('Opening Point Of Sale data for: '+ pos_data_loc)
        with open(pos_data_loc, 'r') as f:
            point_of_sale = yaml.load(f)
    except: # create a new recipe from a template
        msg('No Point of Sale data this time.')
        point_of_sale = None

    return point_of_sale

def augmentFrontMatter(front_matter):
    # add playorder and id values to the recipe
    front_matter_count = len(front_matter)

    playorder = 0
    for item in front_matter:
        playorder +=1
        item['playorder'] = playorder
        item['id'] = "ncx_"+item['name']

        if item['name'] in ['table_of_contents', 'title_page']:
            item['src'] = 'content/'+item['name']+'.xhtml'
            if item['name'] == 'table_of_contents':
                item['properties'] = 'nav'
        else:
            item['src'] = item['name']+'.xhtml'
            item['dir'] = '../'
        if item['name'] not in ['table_of_contents']:
	    # don't have toc as an entry in the toc
            item['toc_entry'] = prettify(item['name'])
        item['tocncx_entry'] = prettify(item['name'])

    msg("front_matter count: "+ str(front_matter_count))
    return front_matter, front_matter_count

def prettify(messy_string):
    # split string into words (using "_") and capitalize each
    words = messy_string.split("_")
    s=""
    for word in words:
        if word not in ['a','of','an','and','or']:
            s = s + word.capitalize()+ ' '
        else:
            s = s + word+ ' '
    s = s[:-1] # remove final space
    return s

def getChapterMetadata(c):
    chapter_metadata = {'id':c['id'],
                        'playorder': c['playorder'],
                        'name': c['name'],
                        'nbr':c['nbr'],
                        'nbr_fmt':c['nbr_fmt'],
						}
    return chapter_metadata

def augmentParts(_recipe):
    # add chapters to the parts section of the recipe, create parts if not existing.
    if 'parts' in _recipe:
        for part in _recipe['parts']:
            msg('PART: '+ str(part))
            part['chp'] = []
            include_chapter_in_part = False
            for c in _recipe['chapters']:
                #msg('  CHAPTER:'+ c['code'])
                if 'starts_part' in c:  # first chapter in a part
                    if c['starts_part'] == part['part_name']:
                        # start of current part
                        starting_chapter = c['nbr_fmt']
                        include_chapter_in_part = True
                    else: # start of next part
                        include_chapter_in_part = False
                else: # this chapter is not the start of a new part
                    #include_chapter_in_part = True
                    pass
                if include_chapter_in_part:
                    msg('  CHAPTER:'+ c['code'])
                    chapter_metadata = getChapterMetadata(c)
                    part['chp'].append(chapter_metadata)
            try:
                part['starting_chapter'] = starting_chapter
            except:
                msg('***ERROR, must define at least one valid starts_part in a recipe***')
                raise SystemExit
            part['chap_toc_style'] = 'toc_chapter_with_parts'
    else: # user entered no parts, so make 1 default part.
        parts_dict = {'name': 'Chapters:', 'chp': [],
                      'starting_chapter': '1',
                      'chap_toc_style': 'toc_chapter_no_parts'}
        for c in _recipe['chapters']:
            chapter_metadata = getChapterMetadata(c)
            parts_dict['chp'].append(chapter_metadata)
        _recipe['parts'] = [parts_dict]

    return _recipe

def augmentBackMatter(_recipe, playorder):
    for item in _recipe['back_matter']:
        playorder +=1
        item['playorder'] = playorder
        item['id'] = "ncx_"+item['name']

        if item['name'] in ['table_of_contents', 'title_page']:
            item['src'] = 'content/'+item['name']+'.xhtml'
        else:
            item['src'] = item['name']+'.xhtml'
            item['dir'] = '../'
        item['toc_entry'] = prettify(item['name'])
        item['tocncx_entry'] = prettify(item['name'])

    return _recipe

def augmentImages(_recipe):
    # create an images section in 'recipe'
    _recipe['images'] = []
    images = _recipe['images']
    id = 0
    # TODO make bulletproof, deal with images in paras and alt words
    all_images = os.listdir(dirs['images'])
    try:
        all_images.remove('Thumbs.db') # not an image
    except:
        pass
    for image in all_images:
        id+=1
        image_name = image[:-4] # trim suffix and dot
        if image_name == 'cover_image':
            images.append({'image': image_name, 'id': 'img'+str(id), 'cover':True})
        else:
	        images.append({'image': image_name, 'id': 'img'+str(id)})

    return _recipe

def augmentFonts():
    # create a fonts section in 'recipe'
    #_recipe['fonts'] = []
    fonts = []
    id = 0

    for font in os.listdir(dirs['fonts']):
        id+=1
        font_name = font.split(".")[0] # trim suffix and dot
        font_type = font.split(".")[1]
        fonts.append({'name': font_name, 'type': font_type, 'id': 'font_'+str(id)})
    return fonts

def cleanChapterMetaData(_recipe):
    # tidy text in chapter meta data
    for chapter in _recipe['chapters']:
        new_text = postMarkdownTextClean(chapter['name'])
        chapter['name'] = new_text
    return _recipe

def determineLinear(_item_name):
    if _item_name in ['cover', 'table_of_contents']:
        linear = 'no'
    else:
        linear = 'yes'
    return linear

def addContentFiles(_recipe):
    # for package.opf spine section
    # add front, back and chapter data to the _recipe
    content_files = []
    for item  in _recipe['front_matter']:
        linear = determineLinear(item['name'])
        content_files.append({'file': item['name'], 'linear': linear})

    for chapter in _recipe['chapters']:
        linear = determineLinear(item['name'])
        content_files.append({'file': "chap"+chapter['nbr_fmt'], 'linear': linear})

    for item  in _recipe['back_matter']:
        linear = determineLinear(item['name'])
        content_files.append({'file': item['name'], 'linear': linear})

    return content_files

def writeAugmentedRecipe(_recipe):
    # write recipe to a file merely for humans to look at should they wish
    if arg2 == 'debug':
        pp = pprint.PrettyPrinter(indent=2)
        entire_structured_book = pprint.pformat(_recipe)
        f = codecs.open(join(dirs['tmp'], 'augmented_'+file_name+'_recipe.json'), 'w', 'utf-8')
        f.write(entire_structured_book)
        f.close()

def getScenesDict(raw_scenes_dir):
    checkForChapterFiles()
    # get ordered list of scenes per chapter from raw dir
    # each file must begin with a chapter id followed by an underscore
    # scenes will be put in alphabetical order by file name within the chapter.
    # desired structure:
    # {'_001': ['0010_scene1',],
    #  '_002': ['0010_scene2','0020_scene3'],
    # }  # the scene numbers are only for the alphabetical order and to allow adding
    #    # new scenes between existing ones without needing to rename everything.
    # raw book files must begin with 3 digits identifying the chapter
    os.chdir(raw_scenes_dir)
    ingredients_list = sorted(glob.glob('./_*.txt'))
    os.chdir('..')
    # put list into a dict.
    scene_dict = {}
    for scene in ingredients_list:
        scene = scene[2:] # remove ".//" from front
        scene = scene[:-4] # remove ".txt" from end
        chapter_id = scene[1:4] # extract chapter id
        try:
            int_chapter_id = int(chapter_id)
            isScene = True
        except:
            isScene = False
            msg('Not a scene:'+ scene)
        if isScene:
            if chapter_id not in scene_dict:
                scene_dict[chapter_id] = []

            scene_dict[chapter_id].append(scene)
    return scene_dict

def checkForChapterFiles():
    # ensure each chapter in the recipe has at least one file, if not
    # create empty file.
    os.chdir(dirs['raw_book'])
    ingredients_list = glob.glob('./_*.txt')
    chapter_code_ingredients = []
    for item in ingredients_list:
        chapter_code_ingredients.append(item[3:6])
    for chapter in recipe['chapters']:
        if chapter['code'] not in chapter_code_ingredients:
            msg('creating new empty chapter:'+ chapter['code'])
            f = open('_'+chapter['code']+'_0010_.txt','w+')
            f.close()
    os.chdir('..')

def genFrontBackMatter(_recipe):
    # for each front/back matter page the recipe name refers to:
    # 1. text from the raw folder,
    # 2. a mustache template from the templates folder,
    # 3. output to an xhtml file in the OEPBS folder, the exceptions are
    #     toc.xhtml and title_page.xhtml which go in the content folder

    for page in _recipe['front_matter'] + _recipe['back_matter']:
        if page['name'] not in ['cover','title_page','table_of_contents']:
            try:
                in_file = open(join(dirs['raw_book'], page['name']+'.txt'), 'r')
            except:  # create empty file
                f = open(os.path.join(dirs['raw_book'], page['name']+'.txt'),'w+')
                f.close()
                # try again (with empty file)
                in_file = open(join(dirs['raw_book'], page['name']+'.txt'), 'r')
            formatted_txt = formatScene(in_file, 0, False)
            _recipe[page['name']] = formatted_txt
        genPage(_recipe, page['name'])
    return _recipe

def manifest_items():
    # TODO: this is a dup of functionality in contentopf.mustache - combine
    items = []
    items.append("toc.ncx")
    for item in recipe['front_matter']:
        items.append(item['src'])
    for item in recipe['chapters']:
        chap_nbr = str("%03d" % (int(item['nbr']),))
        items.append("content/chap"+chap_nbr+".xhtml")
    for item in recipe['back_matter']:
        items.append(item['src'])
    items.append('css/epub-stylesheet.css')
    #items.append('css/kindle-stylesheet.css')
    #items.append('cover_image.jpg')
    for item in recipe['images']:
        items.append("images/"+item['image']+".jpg")
    for font in recipe['fonts']:
        items.append("fonts/"+font['name']+"."+font['type'])
    return items

def createArchive(rootDir, outputPath):
    msg("zipping up to .epub at: "+ outputPath)
    # create served directory if it does not exist.
    createEmptyDir(dirs['epub_loc'], False)
    fout = zipfile.ZipFile(outputPath, 'w')
    cwd = os.getcwd()
    os.chdir(rootDir)
    fout.write('mimetype', compress_type = zipfile.ZIP_STORED)
    fileList = []
    fileList.append(os.path.join('META-INF', 'container.xml'))
    fileList.append(os.path.join('OEBPS', 'package.opf'))

    for itemPath in manifest_items():
        fileList.append(os.path.join('OEBPS', itemPath))
    for filePath in fileList:
        fout.write(filePath, compress_type = zipfile.ZIP_DEFLATED)
    fout.close()
    os.chdir(cwd)

def epubcheck(checkerPath, epubPath):
    if os.name == 'posix': # linux server
        f = open('tmp.txt','w')
        subprocess.call(['epubcheck' + ' ' + epubPath], shell = True, stdout = f) 
        f.close()
        f = open('tmp.txt','r')
        output = f.read()
        msg(output)
        f.close()
    else: 
        subprocess.call(['java', '-jar', checkerPath, epubPath], shell = True)

def kindlegen(checkerPath, epubPath):
    if os.name == 'posix': # linux server
        f = open('tmp.txt','w')
        subprocess.call([checkerPath + ' ' + epubPath], shell = True, stdout = f)
        f.close()
        f = open('tmp.txt','r')
        output = f.read()
        msg(output)
        f.close()
    else:
        subprocess.call([checkerPath, epubPath], shell = True)

#########################################################################
if __name__ == "__main__": # main processing

    createEmptyDir(dirs['tmp'], False)

    recipe = importYaml(file_name)

    prepareDirs(dirs)

    recipe = checkFrontBackMatter(recipe)

    recipe['point_of_sale'] = addPOSData('pos')

    recipe = cleanChapterMetaData(recipe)

    # add data to the recipe front matter
    recipe['front_matter'], front_matter_count = augmentFrontMatter(recipe['front_matter'])

    # prepare a dictionary of scenes
    scenes_dict = getScenesDict(dirs['raw_book'])

    # generate chapters
    # sets chapters and parts
    recipe, next_playorder = genChapters(recipe, front_matter_count, scenes_dict)

    recipe['content_files'] = addContentFiles(recipe)

    # add data to the recipe back_matter
    recipe = augmentBackMatter(recipe, next_playorder)

    recipe = augmentImages(recipe)

    # TODO make others follow this pattern
    recipe['fonts'] = (augmentFonts())

    recipe = augmentParts(recipe)

    recipe = genFrontBackMatter(recipe)

    genPackageOpf(recipe) # generate the content.opf file
    genTocNcx(recipe) # generate the ncx table of contents

    # write the augmented recipe to a file, just for humans to look at
    writeAugmentedRecipe(recipe)
    msg("ePubChef is finished, see /"+file_name+"_served.")

    # zip results into an epub file
    epub_file = join(dirs['epub_loc'], file_name + '.epub')
    createArchive(dirs['gen_dir'], epub_file)
    # Optionally validate the epub
    # NOTE: epubcheck is not part of ePubChef and we won't be offended if you don't run
    # it from here.
    # To validate, install the Java JDK on your machine, set your PATH to include java, and put the epubcheck jar file in the folder above this one.
    # execute cook.py with an additional argument, "python cook.py validate"
    if arg2 in ['validate','kindlegen']:
        epubPath = join(dirs['epub_loc'], file_name + '.epub')
        epubcheck('../epubcheck/epubcheck-3.0.1.jar', epubPath )

    # Optionally run kindlgen to create a .mobi
    # NOTE: kindlgen is not part of ePubChef and we won't be offended if you don't run
    # it from here.
    # To run kindlegen, extract kindlegen to a folder above this one (beside epubchef folder).
    # execute cook.py with an additional argument, "python cook.py kindlegen" (validate will run too)
    if arg2 == 'kindlegen':
        epub_file = join(dirs['epub_loc'], file_name + '.epub')
        if os.name == 'posix': # linux server
            kindlegen('/home/ubuntu/kindlegen/kindlegen', epub_file )
        else:
            # this is the windows command, adjust for other operating systems.
            kindlegen('..\kindlegen_win32_v2_9\kindlegen', epub_file )

    msg("All done\n")
    log.close
