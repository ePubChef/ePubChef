# generate (cook) eBook from "prepared_ingredients" files of the book
# and the file recipe.py in the same folder which drives
# ebook creation.
# call with: python cook demo  # if you book is called 'demo'
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

template_dir = "templates"

# get the recipe file for the book
file_name = sys.argv[1]

# check for a debug level run
try:
    if sys.argv[2] == 'debug':
        debug_run = True
        print('DEBUG level run')
except:
    debug_run = False
    print('not debug')

dirs = {
    'gen_dir': file_name, # folder for the ePub files
    'template_dir':'templates',         # templates for ePub files
	'raw_book': file_name+'_raw', # words and images of the book
	'oebps': file_name+'/OEBPS',
    'raw_images': file_name+'_raw'+'/images',
    'images': file_name+'/OEBPS/images',
	'content': file_name+'/OEBPS/content',
	'css':'css',
	'tmp':'tmp',
	}

''' structure to be generated for book "bk1" is:
  chef/gen_bk1 (generated book root dir)
      mimetype
  gen_bk1//META-INF
     container.xml
  gen_bk1/OEBPS
     content.opf
     cover_image.jpg
     cover.html (not for kindle)
     toc.ncx
  gen_bk1/OEBPS/content
     content001.html
     content...html
     htmloc.html
  gen_bk1/OEBPS/css
     epub-stylesheet.css (change for kindle)
  gen_bk1/OEBPS/images
     ... images
'''    

''' source files are:
  chef (root)
     cook.py
     prepare.py
     recipe.py * (later generate this)
  chef/css
     epub-stylesheet.css
     kindle-stylesheet.css
  chef/raw_book
     chapter_intros.py *
     scene_1.txt *
     scene_....txt *
  chef/raw_book/images
     ...jpg *
  chef/templates
     content.mustache
     json.mustache
     table_of_contents.mustache
     title.mustache
     mimetype
     container.xml
     ....(more)

* = author created book contents
'''

''' temporary files created:
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
of which there can be many, or a "class" which defines the html class of the paragraph.
'''
renderer = pystache.Renderer()

def importYaml(file_name):
    with open(file_name+'_recipe.yaml', 'r') as f:
        doc = yaml.load(f)
    return doc

def createEmptyDir(dir_nm, add_init):
    # create a directory if it does not exist, delete files
    # from it if it already existed.
    # Optionally add an empty __init__.py to the dir.
    if not os.path.exists(dir_nm): # create it if it does not exist
            os.makedirs(dir_nm)
    else:
        # delete contents if it already existed
        print('deleting', dir_nm)
        shutil.rmtree(dir_nm)
    if add_init:
        f = open(os.path.join(dir_nm, '__init__.py'),'w+')
        f.close()
	
def prepareDirs(dirs):
    # delete previous generated folders
    if debug_run:
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
    #image_src = osdirs['raw_book'],'images')
    #image_dst = os.path.join(dirs['oebps'],'images')
    shutil.copytree(dirs['raw_images'], dirs['images']) 
    
	# move the cover image up one level
    src = os.path.join(dirs['oebps'],'images', 'cover_image.jpg')
    dst = os.path.join(dirs['oebps'], 'cover_image.jpg')
    shutil.move(src, dst) 
    
	# ePubChef creation image 
    src = os.path.join(dirs['template_dir'], 'epubchef_logo.jpg')
    dst = os.path.join(dirs['oebps'],'images', 'epubchef_logo.jpg')
    shutil.copyfile(src, dst) 
    
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
    
def formatScene(in_file, scene_count, auto_dropcaps):
    # replace characters we don't like
    lines = [line.strip() for line in in_file]

    style = next_para_style = None
    all_paras = {}
    paras = []

    non_blank_lines = []  # TODO improve this hack to git rid of blank lines
    for line in lines:
        if len(line) > 0:
            non_blank_lines.append(line)

    need_to_clear = False    
    para_count = 0
    for line in non_blank_lines:
        para_class = setParaClass(para_count, scene_count=0)
        para = {}
        textblock = []
        text_class = False # default
        
	# determine if the line is already html and so does not need <p> tags
        if not line.endswith(">"):  # TODO: make this more foolproof
	    # a text line (not HTML)
            para['needs_para_tag'] = True
            line = cleanText(line)
        else:
            # an HTML line
            pass
            #print(line)
        
	# escape odd characters
        line = line.replace("'","&#39;") # single quote
        line = re.sub(r'&(?![#a-zA-Z0-9]+?;)', "&amp;", line) # ampersands
	# double spaces to single
	# three dots ... to an elipsis
        line = line.replace('...',"&#8230;") 
	# culy quotes, double and single
        if line[0] == '"': # a cludge, but it works
            line = " "+ line
        # for every new line create a json paragraph item and fill it with text           
        # split the paragraph into blocks by style to be applied to the text
	
	# drop capitals in the first character
        if auto_dropcaps and scene_count == 0 and para_count == 0: 
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

    prepared_scene = generateJson(all_paras)

    _scene = dict(paras = paras) 
    return _scene

def genPage(recipe, page_name):
    # generate a page (non-chapter page)
    if page_name in ['table_of_contents','title_page']:
        out_dir = 'content'
    else:
        out_dir = 'oebps'

    f = codecs.open(os.path.join(dirs[out_dir], page_name+".html"), 'w', 'utf-8')
    out = renderer.render_path(os.path.join(dirs['template_dir'], 
	    page_name+'.mustache'), recipe)
    f.write(out)
    f.close()

def genContentOpf(book):
    # generate content.opf file 
    f = codecs.open(os.path.join(dirs['oebps'],'content.opf'), 'w', 'utf-8')
    out = renderer.render_path(os.path.join(dirs['template_dir'], 'contentopf.mustache'), book)
    f.write(out)
    f.close()

def genTocNcx(book):
    # generate toc.ncx
    f = codecs.open(os.path.join(dirs['oebps'],'toc.ncx'), 'w', 'utf-8')
    out = renderer.render_path(os.path.join(dirs['template_dir'], 'tocncx.mustache'), book)
    f.write(out)
    f.close()

def genChapters(chapters, front_matter_count, scenes_dict):
    chapter_nbr = 0
    for chapter in chapters:
        chapter_nbr +=1
        chapter['nbr'] = str(chapter_nbr)
        chapter['id'] = 'h2-'+str(chapter_nbr)
        chapter['playorder'] = str(front_matter_count + chapter_nbr)

        scene_nbr = 0
	# TODO: if no raw txt file exists for the chapter, create one (_029_0010_.txt)
        genChapter(chapter, scenes_dict[chapter['code']])
    return chapter_nbr

def genChapter(chapter, scenes):
    chapter['kindle'] = recipe['kindle'] # add the kindle True/False to each 
    # generate the book using templates and the recipe
    chapter['scenes'] = []
    scene_count = 0 # counts the position of the scene in this chapter
                      # for dividers and drop_caps
    for scene_name in scenes:
        #add divider between scenes
        if scene_count > 0:
            chapter['scenes'].append(dict(divider = True))
	# turn the raw text into structured text
        prepared_scene = prepareScene(scene_name, scene_count)
        chapter['scenes'].append(prepared_scene)
        scene_count+=1
    # write the chapter
    f = codecs.open(os.path.join(dirs['content'], 'chap'+chapter['nbr']+'.html'), 'w', 'utf-8')
    #print('CHAPTER:', chapter)
    out = renderer.render_path(os.path.join(dirs['template_dir'], 'chapter.mustache'), chapter)
    #remove blank lines
    out =  "".join([s for s in out.strip().splitlines(True) if s.strip()])
    f.write(out)
    f.close()

def cleanText(line):
    line = line.replace(' "'," &ldquo;") # left double quote
    line = line.replace('<a &ldquo;','<a "') # undo smart quotes on HTML links
    # TODO: add left smart quote if at beginning of a line.
    #line = line.replace('"([a-zA-Z])'," &ldquo;") # left double quote
    #line = re.sub(r'"([a-zA-Z])'," $1&ldquo;", line) # left double quote
    line = line.replace('" ',"&rdquo; ") # right double quote
    line = line.replace('."',"&rdquo;") # right double quote

    # remove tabs
    # leading whitespace
    # trailing whitespace
    # fancy aposthrophes

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
    if debug_run:
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
    in_file = open(join(dirs['raw_book'], scene_name+'.txt'), 'r')
    prepared_scene = formatScene(in_file, scene_count, recipe['auto_dropcaps'])
    in_file.close() 
    #print('\prepared_scene: ', prepared_scene)
    return prepared_scene

def augmentFrontMatter(front_matter, kindle):
    # add playorder and id values to the recipe
    front_matter_count = len(recipe['front_matter'])
    if kindle:
        front_matter_count -= 1 # don't do a coverpage if kindle

    playorder = 0
    for item in front_matter:
        if kindle and item['name'] == 'cover':
            pass # don't include cover on kindle
        else:
            playorder +=1
        item['playorder'] = playorder
        item['id'] = "ncx_"+item['name']
        
        if item['name'] in ['table_of_contents', 'title_page']:
            item['src'] = 'content/'+item['name']+'.html'
        else:
            item['src'] = item['name']+'.html'
            item['dir'] = '../'
        if item['name'] not in ['table_of_contents']: 
	    # don't have toc as an entry in the toc
            item['toc_entry'] = prettify(item['name'])
        item['tocncx_entry'] = prettify(item['name'])
	
    return front_matter_count

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

def augmentBackMatter(back_matter, playorder):
    for item in back_matter:
        playorder +=1
        item['playorder'] = playorder
        item['id'] = "ncx_"+item['name']
        
        if item['name'] in ['table_of_contents', 'title_page']:
            item['src'] = 'content/'+item['name']+'.html'
        else:
            item['src'] = item['name']+'.html'
            item['dir'] = '../'
        item['toc_entry'] = prettify(item['name'])
        item['tocncx_entry'] = prettify(item['name'])
	
def augmentImages(chapters):
    # create an images section in 'recipe'
    recipe['images'] = []
    images = recipe['images']    
    id = 0
    # TODO make bulletproof, deal with images in paras and alt words
    all_images = os.listdir(dirs['images'])
    all_images.remove('Thumbs.db') # not an image
    #print('images:', all_images)
    for image in all_images:
        id+=1
        image_name = image[:-4] # trim suffix and dot
        images.append({'image': image_name, 'id': 'img'+str(id)})

def addContentFiles(_recipe):
# for content.opf spine section
    # add front, back and chapter data to the _recipe
    _recipe['content_files'] = []
    for item  in _recipe['front_matter']:
            #name = item #['src'][:-5] #strip off ".html"
            #name = name.split("/")[-1] # strip off any path
            _recipe['content_files'].append({'file': item['name']})
    
    for chapter in _recipe['chapters']:
        _recipe['content_files'].append({'file': "chap"+chapter['nbr']})

    for item  in _recipe['back_matter']:
	    #name = item  #['src'][:-5] #strip off ".html"
	    #name = name.split("/")[-1] # strip off any path
	    _recipe['content_files'].append({'file': item['name']})
    return _recipe

def writeAugmentedRecipe(recipe):
    # this is merely for humans to look at should they wish
    if debug_run:
        pp = pprint.PrettyPrinter(indent=2)
        entire_structured_book = pprint.pformat(recipe)
        f = codecs.open(join(dirs['tmp'], 'augmented_'+file_name+'_recipe.json'), 'w', 'utf-8')
        f.write(entire_structured_book)
        f.close()

def getScenesDict(raw_scenes_dir):
    # get ordered list of scenes per chapter from raw dir 
    # each file must begin with a chapter id followed by an underscore
    # scenes will be put in alphabetical order by file name within the chapter.
    # desired structure:
    # {'_001': ['0010_scene1',],
    #  '_002': ['0010_scene2','0020_scene3'],
    # }  # the scene numbers are only for the alphabetical order and to allow adding
    #    # new scenes between existing ones wihout needing to rename everything.
    # raw book files must begin with 3 digits identifying the chapter
    os.chdir(raw_scenes_dir)
    ingredients_list = glob.glob('./_*.txt')
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
            print ("chapter",chapter_id,scene)
            if chapter_id not in scene_dict:
                scene_dict[chapter_id] = []
            
            scene_dict[chapter_id].append(scene)
    #print("\nscene_dict:", scene_dict)
    return scene_dict

#########################################################################
if __name__ == "__main__": # main processing

    recipe = importYaml(file_name)

    prepareDirs(dirs)

    # TODO: ensure scenes are always in the correct order - from glob
   
    # add data to the recipe front matter
    front_matter_count = augmentFrontMatter(
	recipe['front_matter'], recipe['kindle'])
    print("front-matter count:", front_matter_count)

    # prepare a dictionary of scenes 
    scenes_dict = getScenesDict(dirs['raw_book'])

    # generate chapters 
    chapter_count = genChapters(recipe['chapters'], front_matter_count, scenes_dict)
    print("chapter count: ", chapter_count)
 
    recipe = addContentFiles(recipe)
    
    # add data to the recipe backmatter
    augmentBackMatter(recipe['back_matter'],
	front_matter_count + chapter_count)

    augmentImages(recipe['chapters'])
    
    # for each front/back matter page the recipe name refers to:
    # 1. text from the raw folder,
    # 2. a mustache template from the templates folder,
    # 3. output to an html file in the OEPBS folder, the exceptions are
    #     toc.html and title_page.html which go in the content folder

    for page in recipe['front_matter'] + recipe['back_matter']:
        if page['name'] not in ['cover','title_page','table_of_contents']:
            in_file = open(join(dirs['raw_book'], page['name']+'.txt'), 'r')
            formatted_txt = formatScene(in_file, 0, False)
            recipe[page['name']] = formatted_txt
        genPage(recipe, page['name'])

    genContentOpf(recipe) # generate the content.opf file
    genTocNcx(recipe) # generate the ncx table of contents

    # write the augmented recipe to a file, just for humans to look at
    writeAugmentedRecipe(recipe)
    print("done")
