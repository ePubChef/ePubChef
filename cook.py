'''
ePubChef - generating EPUB files for eBooks
    Copyright (C) 2014  John Cobo
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
# generate (cook) eBook from "prepared_ingredients" files of the book
# and the file recipe.py in the same folder which drives
# ebook creation.
# call with: python cook.py demo  # if you book is called 'demo'. 
# Optional second arguments are "debug", or "validate", or "kindlegen" eg. python cook.py demo validate

# debug populates a /debug directory, validate runs EPUB check if it has been set up (Java, etc.)
# Output generated to the directory specified by the 'file_name' from recipe.py.

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

template_dir = "templates"

# get the recipe file for the book
file_name = sys.argv[1]

# check for a debug level and validate run
arg2 = None
try:
    arg2 = sys.argv[2]
except:
    pass

gen_dir = file_name+'_generated'

dirs = {
    'gen_dir': gen_dir, # folder for the ePub files
    'template_dir':'templates',         # templates for ePub files
	'raw_book': file_name+'_raw', # words and images of the book
	'oebps': gen_dir+'/OEBPS',
    'raw_images': file_name+'_raw'+'/images',
    'images': gen_dir+'/OEBPS/images',
    'default_cover': 'demo_raw/images',
	'content': gen_dir+'/OEBPS/content',
	'css':'css',
	'tmp':'debug',
    'epub_loc': 'epubs',
    'raw_fonts': file_name+'_raw'+'/fonts',
    'fonts': gen_dir+'/OEBPS/fonts',
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
     mybook_recipe.yaml
     _0010_010_scene....txt (many scene files) 
  /mybook_raw/images
     ...jpg *
  /mybook_raw/fonts
     ...otf
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
    try:
        recipe_loc = os.path.join(file_name+'_raw', file_name+'_recipe.yaml')
        print('Opening recipe for:', recipe_loc)
        with open(recipe_loc, 'r') as f:
            _recipe = yaml.load(f)
    except: # create a new recipe from a template
        print('Creating new recipe for:', file_name)
        try:
            f = open(join(dirs['raw_book'], file_name+'_recipe.yaml'), 'w')
        except:   # create the dir if it did not exist
            os.makedirs(dirs['raw_book'])
            f = open(join(dirs['raw_book'], file_name+'_recipe.yaml'), 'w')

        new_recipe = renderer.render_path(os.path.join(dirs['template_dir'], 'recipe.mustache'), dict([("file_name", file_name)]))

        f.write(new_recipe)
        f.close()
        with open(join(dirs['raw_book'], file_name+'_recipe.yaml'), 'r') as f:
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
        print('deleting previously generated directory:', dir_nm)
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
        print('RUNNING in DEBUG mode, see folder: /', dirs['tmp'])
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
        src = 'demo_raw/images/cover_image.jpg'
        shutil.copyfile(src, dirs['raw_images']+'/cover_image.jpg')
       
        # try again now that chapters and cover image has been created
        shutil.copytree(dirs['raw_images'], dirs['images']) 
    
	# ePubChef creation image 
    src = os.path.join(dirs['template_dir'], 'epubchef_logo.jpg')
    dst = os.path.join(dirs['oebps'],'images', 'epubchef_logo.jpg')
    shutil.copyfile(src, dst) 
    
    # fonts
    try:
        shutil.copytree(dirs['raw_fonts'], dirs['fonts']) 
    except: # create ..._raw and ..._raw/fonts if they don't exist
        #os.makedirs(dirs['raw_fonts'])
        src = 'demo_raw/fonts'
        shutil.copytree(src, dirs['raw_fonts'])
        # try again
        shutil.copytree(dirs['raw_fonts'], dirs['fonts']) 
        
    # css
    css_src = dirs['css']
    css_dst = os.path.join(dirs['oebps'],'css')
    shutil.copytree(css_src, css_dst) 
    
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
    for n in range(1,4):
        if _line[0:n] in ["####", "###", "##", "#"]:
            _line = markdown.markdown("#"+_line)
    # lists
    
    return _line
    
def groupMarkdown(_n, lines):
    # some markdown such as lists and tables use more than one line from the input file.
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
        line = markdown.markdown(line)
        
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
    #print("nonblanks:",non_blank_lines, len(non_blank_lines))
    #lines = non_blank_lines
    #nbr_lines = 
    #for n in range(0,len(lines)):
    n = 0
    while n < len(non_blank_lines):
        line = non_blank_lines[n]
        para_class = setParaClass(para_count, scene_count=0)
        para = {}
        textblock = []
        text_class = False # default
        
        # group together markdown which should be processed as one line, eg. one HTML entity such as a list or table.
        n, line = groupMarkdown(n,non_blank_lines)
        line = processMarkdown(line)

            
	    # determine if the line is already xhtml and so does not need <p> tags
        if not line.endswith(">"):  # TODO: make this more foolproof
	    # a text line (not XHTML)
            para['needs_para_tag'] = True
            line = cleanText(line)
        else:
            # an xhtml line
            pass
            #print(line)
        
	    # escape odd characters
        line = line.replace("'","&#39;") # single quote
        line = re.sub(r'&(?![#a-zA-Z0-9]+?;)', "&#38;", line) # ampersands
	    # double spaces to single
        # TODO double spaces to single
	    # three dots ... to an elipsis
        line = line.replace('...',"&#8230;") 
	    # curly quotes, double and single
        if line[0] == '"': # a cludge, but it works
            line = " "+ line
        # for every new line create a json paragraph item and fill it with text           
        # split the paragraph into blocks by style to be applied to the text
	
	    # drop capitals in the first character of a chapter
        if auto_dropcaps and scene_count == 0 and para_count == 0 and line[0] not in ['&']: 
	        # a drop capital
            drop_letter, line, text_class = dropCap(line)
            drop_text_block = block(para, para_class, text_class, drop_letter)
            textblock.append(drop_text_block)
            text_class = False # default
        elif line[0:3] == ">>>":  # a block quote
            line, para_class = blockquote(line)

        # text_class and words
        std_text_block = block(para, para_class, text_class, line)
        textblock.append(std_text_block)
        para_count +=1
        
        para['textblock'] = textblock
        paras.append(para)
        all_paras['paras'] = paras
 
        n+=1
        
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
    #if part_nbr > 1: # don't increment if there is only the default part.
    #    next_playorder = next_playorder +1
    
    print("chapter count: ", chapter_nbr)
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
    f = codecs.open(os.path.join(dirs['content'], 'chap'+_chapter['nbr']+'.xhtml'), 'w', 'utf-8')
    #print('CHAPTER:', _chapter)
    out = renderer.render_path(os.path.join(dirs['template_dir'], 'chapter.xhtml'), _chapter)
    #remove blank lines
    out =  "".join([s for s in out.strip().splitlines(True) if s.strip()])
    f.write(out)
    f.close()
    
    return _chapter

def cleanText(line):
    # left double quotes
    line = line.replace(' "'," &#8220;") # replace straight double quote following a space with left smart quote
    if line[0] == '"': # replace straight double quote at start of a line with a left smart quote
        line = line.replace('"',"&#8220;", 1)
    
    line = line.replace('<a &#8220;','<a "') # undo smart quotes on xhtml links
    
    # right double quotes
    line = line.replace('" ',"&#8221; ") # replace straight double quote preceding a space with a right smart quote
    # end of paragraphs
    line = line.replace('."',".&#8221;") # replace straight double quote following a period with a right smart quote
    line = line.replace('?"',"?&#8221;") # replace straight double quote following a question mark with a right smart quote
    line = line.replace('!"',"!&#8221;") # replace straight double quote following a exclamation with a right smart quote
    
    # undo smart quotes on image xhtml links - part one
    line = line.replace('.jpg&#8221;','.jpg"') 
    # undo smart quotes on image xhtml links - part two
    line = line.replace('&#8221;/>','"/>') 
    # undo smart quotes on image xhtml links - part three
    line = line.replace('&#8221; alt=','" alt=') 

    # left single quotes
    line = line.replace(" '"," &#8216;") # replace straight single quote following a space with left smart quote
    if line[0] == "'": # replace straight single quote at start of a line with a left smart quote
        line = line.replace("'","&#8216;", 1)
    
    # right single quotes
    line = line.replace("' ","&#8217; ") # replace straight single quote preceding a space with a right smart quote
    line = line.replace(".'",".&#8217;") # replace straight single quote following a period with a right smart quote

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
	
def blockquote(line):
    # deal with blockquote instructions ( >>> )
    line = line[3:] # remove formatting 
    para_class = 'blockquote'
    return line, para_class
	
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
    #print('\prepared_scene: ', prepared_scene)
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
        print('front_matter:', _recipe['front_matter'])
        raise Exception("You must have 'cover' in front_matter!")
        
    if {'name':'title_page'} not in _recipe['front_matter']:
        print('front_matter:', _recipe['front_matter'])
        raise Exception("You must have 'title_page' in front_matter!")
        
    if {'name':'table_of_contents'} not in _recipe['front_matter']:
        print('front_matter:', _recipe['front_matter'])
        raise Exception("You must have 'table_of_contents' in front_matter!")
        
    for fname in _recipe['front_matter'] + _recipe['back_matter'] :
        # create a dummy template if none exist
        if not os.path.isfile(join(dirs['template_dir'],fname['name']+'.xhtml')):
            src = join(dirs['template_dir'], 'template_template.xhtml')
            dst = join(dirs['template_dir'], fname['name']+'.xhtml')
            shutil.copyfile(src, dst)
    return _recipe
    
def addPOSData(_recipe, pos_data_loc):
    # adds last second Point Of Sale data to the recipe.
    # pos_data_loc is a file system or http location of date to add to the recipe
    # it must be YAML file similar to the book recipe file. It will be appended to the recipe
    # TODO: augment to read from a URL or as input to this job
    # local file read works fine for demonstrations.
    try:
        pos_data_loc = os.path.join(file_name+'_raw', file_name+'_pos_data.yaml')
        print('Opening Point Of Sale data for:', pos_data_loc)
        with open(pos_data_loc, 'r') as f:
            _recipe['point_of_sale'] = yaml.load(f)
    except: # create a new recipe from a template
        print('No Point of Sale data this time.')
        
    return _recipe
    
def augmentFrontMatter(_recipe):
    # add playorder and id values to the recipe
    front_matter_count = len(_recipe['front_matter'])

    playorder = 0
    for item in _recipe['front_matter']:
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
	
    print("front_matter count:", front_matter_count)
    return _recipe, front_matter_count

def prettify(messy_string):
    # split string into words (using "_") and capilatize each
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
                        'nbr':c['nbr']}
    return chapter_metadata
    
def augmentParts(_recipe):
    # add chapters to the parts section of the recipe, create parts if not existing.
    if 'parts' in _recipe:
        #print('has parts:')
        
        for part in _recipe['parts']:
            print('PART:', part)
            part['chp'] = []
            include_chapter_in_part = False
            for c in _recipe['chapters']:
                print('  CHAPTER:', c['code'])
                if 'starts_part' in c:  # first chapter in a part
                    if c['starts_part'] == part['part_name']: 
                        # start of current part
                        starting_chapter = c['nbr']
                        include_chapter_in_part = True
                    else: # start of next part
                        include_chapter_in_part = False
                else: # this chapter is not the start of a new part
                    #include_chapter_in_part = True
                    pass
                if include_chapter_in_part:
                    print('  score:', part['part_name'], c['code'])
                    chapter_metadata = getChapterMetadata(c)
                    part['chp'].append(chapter_metadata)
            part['starting_chapter'] = starting_chapter
            part['chap_toc_style'] = 'toc_chapter_with_parts'          
    else: # user entered no parts, so make 1 default part.
        parts_dict = {'name': 'Chapters:', 'chp': [], 
                      'starting_chapter': '1',
                      'chap_toc_style': 'toc_chapter_no_parts'}
        for c in _recipe['chapters']:
            chapter_metadata = getChapterMetadata(c)
            parts_dict['chp'].append(chapter_metadata)
        _recipe['parts'] = [parts_dict]
         
    #print ('parts:', _recipe['parts'])
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
    #print('images:', all_images)
    for image in all_images:
        id+=1
        image_name = image[:-4] # trim suffix and dot
        if image_name == 'cover_image':
            images.append({'image': image_name, 'id': 'img'+str(id), 'cover':True})
        else:
	        images.append({'image': image_name, 'id': 'img'+str(id)})
        
    return _recipe
    
def augmentFonts(_recipe):
    # create a fonts section in 'recipe'
    _recipe['fonts'] = []
    fonts = _recipe['fonts']    
    id = 0
    all_fonts = os.listdir(dirs['fonts'])
    #print('fonts:', all_fonts)
    for font in all_fonts:
        id+=1
        font_name = font[:-4] # trim suffix and dot
        fonts.append({'font': font_name, 'id': 'fnt'+str(id)})       
    return _recipe

def determineLinear(_item_name):
    if _item_name in ['cover', 'table_of_contents']:
        linear = 'yes'
    else:
        linear = 'no'
    return linear
    
def addContentFiles(_recipe):
    # for package.opf spine section
    # add front, back and chapter data to the _recipe
    _recipe['content_files'] = []
    for item  in _recipe['front_matter']:
        linear = determineLinear(item['name'])
        _recipe['content_files'].append({'file': item['name'], 'linear': linear})
    
    for chapter in _recipe['chapters']:
        linear = determineLinear(item['name'])
        _recipe['content_files'].append({'file': "chap"+chapter['nbr'], 'linear': linear})
        
    for item  in _recipe['back_matter']:
        linear = determineLinear(item['name'])
        _recipe['content_files'].append({'file': item['name'], 'linear': linear})
        
    return _recipe

def writeAugmentedRecipe(_recipe):
    # write recipe to a file merely for humans to look at should they wish
    if arg2 == 'debug':
        pp = pprint.PrettyPrinter(indent=2)
        entire_structured_book = pprint.pformat(_recipe)
        f = codecs.open(join(dirs['tmp'], 'augmented_'+file_name+'_recipe.json'), 'w', 'utf-8')
        f.write(entire_structured_book)
        f.close()

def getScenesDict(raw_scenes_dir):
    # TODO change raw_scenes_dir to dirs['raw_book']
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
    #print(ingredients_list)
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
            print('Not a scene:', scene)
        if isScene:
            #print ("  processing scene:",chapter_id,scene)
            if chapter_id not in scene_dict:
                scene_dict[chapter_id] = []
            
            scene_dict[chapter_id].append(scene)
    #print("\nscene_dict:", scene_dict)
    return scene_dict

def checkForChapterFiles():
    # ensure each chapter in the recipe has at least one file, if not
    # create empty file.
    os.chdir(dirs['raw_book'])
    ingredients_list = glob.glob('./_*.txt')
    chapter_code_ingredients = []
    for item in ingredients_list:
        chapter_code_ingredients.append(item[3:6])
    #print('existing raw text files:', ingredients_list, chapter_code_ingredients)
    for chapter in recipe['chapters']:
        if chapter['code'] not in chapter_code_ingredients:
            print('creating new empty chapter:', chapter['code'])
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
        items.append("content/chap"+item['nbr']+".xhtml")
    for item in recipe['back_matter']:
        items.append(item['src'])
    items.append('css/epub-stylesheet.css')
    #items.append('css/kindle-stylesheet.css')
    #items.append('cover_image.jpg')
    for item in recipe['images']:
        items.append("images/"+item['image']+".jpg")
    for item in recipe['fonts']:
        items.append("fonts/"+item['font']+".otf")
    return items
    
def createArchive(rootDir, outputPath):
    print("zipping up to .epub")
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
    subprocess.call(['java', '-jar', checkerPath, epubPath], shell = True)
        
def kindlegen(checkerPath, epubPath):
    subprocess.call([checkerPath, epubPath], shell = True)
    
#########################################################################
if __name__ == "__main__": # main processing

    createEmptyDir(dirs['tmp'], False)
        
    recipe = importYaml(file_name)
    
    prepareDirs(dirs)
   
    recipe = checkFrontBackMatter(recipe)
    
    recipe = addPOSData(recipe, 'pos')
    
    # add data to the recipe front matter
    recipe, front_matter_count = augmentFrontMatter(recipe)

    # prepare a dictionary of scenes 
    scenes_dict = getScenesDict(dirs['raw_book'])

    # generate chapters 
    recipe, next_playorder = genChapters(recipe, front_matter_count, scenes_dict)
    
    recipe = addContentFiles(recipe)
    
    # add data to the recipe back_matter
    recipe = augmentBackMatter(recipe, next_playorder)

    recipe = augmentImages(recipe)
    
    recipe = augmentFonts(recipe)

    recipe = augmentParts(recipe)
    
    recipe = genFrontBackMatter(recipe)
    
    genPackageOpf(recipe) # generate the content.opf file
    genTocNcx(recipe) # generate the ncx table of contents

    # write the augmented recipe to a file, just for humans to look at
    writeAugmentedRecipe(recipe)
    print("ePubChef is finished, see /epubs.")
    
    # zip results into an epub file 
    epub_file = join(dirs['epub_loc'], file_name + '.epub')
    createArchive(dirs['gen_dir'], epub_file)
    
    # Optionally validate the epub
    # NOTE: epubcheck is not part of ePubChef and we won't be offended if you don't run 
    # it from here. 
    # To validate, install the Java JDK on your machine, set your PATH to include java, and put the epubcheck jar file in the folder above this one.
    # execute cook.py with an additional argument, "python cook.py validate"
    if arg2 in ['validate','kindlegen']:
        epub_file = join(dirs['epub_loc'], file_name + '.epub')
        epubcheck('../epubcheck/epubcheck-3.0.1.jar', epub_file )
    
    # Optionally run kindlgen to create a .mobi
    # NOTE: kindlgen is not part of ePubChef and we won't be offended if you don't run 
    # it from here. 
    # To run kindlegen, extract kindlegen to a folder above this one (beside epubchef folder).
    # execute cook.py with an additional argument, "python cook.py kindlegen" (validate will run too)
    if arg2 == 'kindlegen':
        epub_file = join(dirs['epub_loc'], file_name + '.epub')
        # this is the windows command, adjust for other operating systems.
        kindlegen('..\kindlegen_win32_v2_9\kindlegen', epub_file )
        
    print("All done\n")