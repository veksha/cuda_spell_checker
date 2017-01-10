# coding: utf8
import os
import sys
import string
import json
from .jsoncomment import JsonComment
from cudatext import *

json_parser = JsonComment(json)

filename_ini = os.path.join(app_path(APP_DIR_SETTINGS), 'cuda_spell_checker.ini')
op_lang = ini_read(filename_ini, 'op', 'lang', 'en_US')
op_underline_color = ini_read(filename_ini, 'op', 'underline_color', '#FF0000')
op_underline_style = ini_read(filename_ini, 'op', 'underline_style', '6')
op_confirm_esc = ini_read(filename_ini, 'op', 'confirm_esc_key', '0')
op_file_types = ini_read(filename_ini, 'op', 'file_extension_list', '*')

sys.path.append(os.path.dirname(__file__))
try:
    import enchant
    dict_obj = enchant.Dict(op_lang)
except Exception as ex:
    msg_box(str(ex), MB_OK+MB_ICONERROR)


MARKTAG = 105 #uniq int for all marker plugins


def is_word_char(s):
    return s.isalpha() or (s in "'_"+string.digits)
    
def is_word_alpha(s):
    if not s: return False    
    #don't allow digit in word
    #don't allow lead-quote
    digits = string.digits+'_'
    for ch in s:
        if ch in digits: return False
    if s[0] in "'": return False
    return True    

def string_to_color(s):
    """ converts #RRGGBB or #RGB to integers"""
    s = s.strip()
    while s[0] == '#': s = s[1:]
    # get bytes in reverse order to deal with PIL quirk
    if len(s)==3:
        s = s[0]*2 + s[1]*2 + s[2]*2
    if len(s)!=6:
        raise Exception('Incorrect color token: '+s)
    s = s[-2:] + s[2:4] + s[:2]
    # finally, make it numeric
    color = int(s, 16)
    return color


def dlg_spell(sub):
    rep_list = dict_obj.suggest(sub)
    en_list = bool(rep_list)
    if not en_list: rep_list=[]
    
    c1 = chr(1)
    id_edit = 3
    id_list = 5
    id_skip = 6
    id_replace = 7
    id_add = 8
    id_cancel = 9
    res = dlg_custom('Misspelled word', 426, 306, '\n'.join([]
        +[c1.join(['type=label', 'pos=6,8,100,0', 'cap=Not found:'])]
        +[c1.join(['type=edit', 'pos=106,6,300,0', 'cap='+sub, 'props=1,0,1'])]
        +[c1.join(['type=label', 'pos=6,38,100,0', 'cap=C&ustom text:'])]
        +[c1.join(['type=edit', 'pos=106,36,300,0', 'val='])]
        +[c1.join(['type=label', 'pos=6,68,100,0', 'cap=Su&ggestions:'])]
        +[c1.join(['type=listbox', 'pos=106,66,300,300', 'items='+'\t'.join(rep_list), 'val='+('0' if en_list else '-1')])]
        +[c1.join(['type=button', 'pos=306,66,420,0', 'cap=&Ignore', 'props=1'])]
        +[c1.join(['type=button', 'pos=306,96,420,0', 'cap=&Change'])]
        +[c1.join(['type=button', 'pos=306,126,420,0', 'cap=&Add'])]
        +[c1.join(['type=button', 'pos=306,186,420,0', 'cap=Cancel'])]
        ), 3)
    if res is None: return
    res, text = res
    text = text.splitlines()
    
    if res==id_skip:
        return ''
        
    if res==id_add:
        dict_obj.add_to_pwl(sub)
        return ''
        
    if res==id_replace:
        word = text[id_edit]
        if word:
            return word
        if en_list: 
            return rep_list[int(text[id_list])]
        else:
            return ''
            
#print(dlg_spell('tst'))        


def dlg_select_dict():
    items = sorted(enchant.list_languages())
    global op_lang
    if op_lang in items:
        focused = items.index(op_lang)
    else:
        focused = -1    
    res = dlg_menu(MENU_LIST, '\n'.join(items), focused)
    if res is None: return
    return items[res]
    

def get_styles_of_editor():
    lexer = ed.get_prop(PROP_LEXER_FILE)
    if not lexer: return
    res = []
    s1 = lexer_proc(LEXER_GET_STYLES_COMMENTS, lexer)
    s2 = lexer_proc(LEXER_GET_STYLES_STRINGS, lexer)
    if s1: res += s1.split(',')
    if s2: res += s2.split(',')
    print('Spellcheck: styles of lexer "%s": %s'%(lexer, res))
    return res
    
#print(get_styles_of_editor()) #debug


def is_filetype_ok(fn):
    global op_file_types
    if op_file_types=='': return False
    if op_file_types=='*': return True
    if fn=='': return True #allow in untitled tabs
    fn = os.path.basename(fn)
    n = fn.rfind('.')
    if n<0: return True #allow if no extension
    fn = fn[n+1:]
    return ','+fn+',' in ','+op_file_types+','


def do_check_line(ed, nline, pos_from, pos_to, 
    styles, with_dialog,
    count_all, count_replace, 
    COLOR_FORE, COLOR_UNDER, BORDER_UNDER):
    """Checks one line, pos_from...pos_to"""
    
    line = ed.get_text_line(nline)
    n1 = pos_from-1
    while True:
        n1 += 1
        if n1>=len(line): break
        if n1>pos_to: break
        if not is_word_char(line[n1]): continue
        n2 = n1+1
        while n2<len(line) and is_word_char(line[n2]): n2+=1
            
        #strip quote from begin of word
        if line[n1]=="'": n1 += 1
        #strip quote from end of word
        if line[n2-1]=="'": n2 -= 1
            
        text_x = n1
        text_y = nline

        sub = line[n1:n2]
        n1 = n2

        token = ed.get_token(TOKEN_AT_POS, text_x, text_y)
        if token:
            ((start_x, start_y), (end_x, end_y), str_token, str_style) = token
            if not str_style in styles: continue
            
        if not is_word_alpha(sub): continue
        if dict_obj.check(sub): continue

        count_all += 1            
        if with_dialog:
            ed.set_caret(text_x, text_y, text_x+len(sub), text_y)
            rep = dlg_spell(sub)
            if rep is None: break
            if rep=='': continue
            count_replace += 1
            ed.delete(text_x, text_y, text_x+len(sub), text_y)
            ed.insert(text_x, text_y, rep)
            #replace
            line = ed.get_text_line(nline)
            n1 += len(rep)-len(sub)
        else:
            ed.attr(MARKERS_ADD, MARKTAG, text_x, text_y, len(sub),   
              COLOR_FORE,
              COLOR_NONE, 
              COLOR_UNDER, 
              0, 0, 0, 0, 0, BORDER_UNDER)
              
    return (count_all, count_replace)


def do_work(with_dialog=False):
    global op_underline_color
    global op_underline_style
    global op_confirm_esc
    COLOR_FORE = ed.get_prop(PROP_COLOR, 'EdTextFont')
    COLOR_UNDER = string_to_color(op_underline_color)
    BORDER_UNDER = int(op_underline_style)
    
    ed.attr(MARKERS_DELETE_BY_TAG, MARKTAG)
    styles = get_styles_of_editor()
    count_all = 0
    count_replace = 0
    total_lines = ed.get_line_count()
    percent = 0
    app_proc(PROC_SET_ESCAPE, '0')
    
    caret_pos = ed.get_carets()[0]
    x1, y1, x2, y2 = caret_pos
    is_selection = y2>=0
    if not is_selection:
        x1 = 0
        y1 = 0
        x2 = 0xFFFFFF
        y2 = ed.get_line_count()-1
    else:
        if (y1>y2) or (y1==y2 and x1>x2):
            x1, y1, x2, y2 = x2, y2, x1, y1
    
    for nline in range(y1, y2+1):
        percent_new = nline * 100 // total_lines
        if percent_new!=percent:
            percent = percent_new
            msg_status('Spell-checking %d%%'% percent)
            if app_proc(PROC_GET_ESCAPE, ''):
                app_proc(PROC_SET_ESCAPE, '0')
                if op_confirm_esc=='0' or msg_box('Stop spell-checking?', MB_OKCANCEL+MB_ICONQUESTION)==ID_OK:
                    msg_status('Spell-check stopped')
                    return

        local_from = 0 if nline!=y1 else x1
        local_to = 0xFFFFFF if nline!=y2 else x2
        
        count_all, count_replace = do_check_line(ed, nline, 
            local_from, local_to,
            styles, with_dialog,
            count_all, count_replace, 
            COLOR_FORE, COLOR_UNDER, BORDER_UNDER)
    
    global op_lang
    msg_sel = 'selection only' if is_selection else 'all text' 
    msg_status('Spell-check: %s, %s, %d mistakes, %d replaces' % (op_lang, msg_sel, count_all, count_replace))
    ed.set_caret(caret_pos[0], caret_pos[1])


def do_work_if_name(ed_self):
    if is_filetype_ok(ed_self.get_filename()): 
        do_work()


def do_work_word(with_dialog):
    global op_underline_color
    global op_underline_style
    COLOR_FORE = ed.get_prop(PROP_COLOR, 'EdTextFont')
    COLOR_UNDER = string_to_color(op_underline_color)
    BORDER_UNDER = int(op_underline_style)

    x, y, x2, y2 = ed.get_carets()[0]
    line = ed.get_text_line(y)
    if not line: return

    if not (0 <= x < len(line)) or not is_word_char(line[x]):
        msg_status('Caret not on word-char')
        return
        
    n1 = x
    n2 = x
    while n1>0 and is_word_char(line[n1-1]): n1-=1
    while n2<len(line)-1 and is_word_char(line[n2+1]): n2+=1
    x = n1
                                
    sub = line[n1:n2+1]
    if not is_word_alpha(sub):
        msg_status('Not text-word under caret')
        return
        
    if dict_obj.check(sub):
        msg_status('Word ok: "%s"' % sub)
        return

    msg_status('Word misspelled: "%s"' % sub)
    if with_dialog:
        ed.set_caret(x, y, x+len(sub), y)
        rep = dlg_spell(sub)
        if rep is None: return
        if rep=='': return
        ed.delete(x, y, x+len(sub), y)
        ed.insert(x, y, rep)
    else:
        ed.attr(MARKERS_ADD, MARKTAG, x, y, len(sub),   
          COLOR_FORE,
          COLOR_NONE, 
          COLOR_UNDER, 
          0, 0, 0, 0, 0, BORDER_UNDER)
        
    ed.set_caret(x, y) 
    

def get_next_pos(x1, y1, is_next):
    m = ed.attr(MARKERS_GET)
    if not m: return
    m = [(x, y) for (tag, x, y, nlen, c1, c2, c3, f1, f2, f3, b1, b2, b3, b4) in m if tag==MARKTAG]
    if not m: return
    
    if is_next:
        m = [(x, y) for (x, y) in m if (y>y1) or ((y==y1) and (x>x1))]
        if m: return m[0]
    else:
        m = [(x, y) for (x, y) in m if (y<y1) or ((y==y1) and (x<x1))]
        if m: return m[len(m)-1]
       
    
def do_goto(is_next):
    x1, y1, x2, y2 = ed.get_carets()[0]
    m = get_next_pos(x1, y1, is_next)
    if m:
        ed.set_caret(m[0], m[1])
        msg_status('Go to misspelled: %d:%d' % (m[1]+1, m[0]+1))
    else:
        msg_status('Cannot go to next/prev')
    


class Command:
    active = False

    def check(self):
        do_work()
    
    def check_suggest(self):
        do_work(True)
        
    def check_word(self):
        do_work_word(False)
    
    def check_word_suggest(self):
        do_work_word(True)
    
    def on_change_slow(self, ed_self):
        do_work_if_name(ed_self)

    def toggle_hilite(self):
        self.active = not self.active
        if self.active:
            ev = 'on_change_slow'
            do_work_if_name(ed)
        else:
            ev = ''
            ed.attr(MARKERS_DELETE_BY_TAG, MARKTAG)
        app_proc(PROC_SET_EVENTS, 'cuda_spell_checker;'+ev+';;')
        
        text = 'Underlines on' if self.active else 'Underlines off'
        msg_status(text) 

    def select_dict(self):
        res = dlg_select_dict()
        if res is None: return
        global filename_ini
        global op_lang
        global dict_obj
        op_lang = res
        ini_write(filename_ini, 'op', 'lang', op_lang)
        dict_obj = enchant.Dict(op_lang)
        if self.active:
            do_work_if_name(ed)
            
    def edit_config(self):
        global op_lang
        global op_underline_color
        global op_underline_style
        global op_confirm_esc
        global op_file_types
        global filename_ini
        ini_write(filename_ini, 'op', 'lang', op_lang)
        ini_write(filename_ini, 'op', 'underline_color', op_underline_color)
        ini_write(filename_ini, 'op', 'underline_style', op_underline_style)
        ini_write(filename_ini, 'op', 'confirm_esc_key', op_confirm_esc)
        ini_write(filename_ini, 'op', 'file_extension_list', op_file_types)
        if os.path.isfile(filename_ini):
            file_open(filename_ini)

    def goto_next(self):
        do_goto(True)
    def goto_prev(self):
        do_goto(False)
        