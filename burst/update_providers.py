# -*- coding: utf-8 -*-
import os
from .client import Client
from kodi_six import xbmc, xbmcvfs, xbmcgui, xbmcaddon, py2_encode

try:
    from xbmcvfs import translatePath
except ImportError:
    from xbmc import translatePath

addon = xbmcaddon.Addon()
id = addon.getAddonInfo('id')
name = addon.getAddonInfo('name')
icon = addon.getAddonInfo('icon')

path_settings = translatePath(os.path.join('special://home/addons/script.elementum.rajada/resources/settings.xml'))
path_json = translatePath(os.path.join('special://home/addons/script.elementum.rajada/burst/providers/providers.json'))

content_settings = 'https://raw.githubusercontent.com/addon-rajada/script.elementum.rajada/master/resources/settings.xml'
content_json = 'https://raw.githubusercontent.com/addon-rajada/script.elementum.rajada/master/burst/providers/providers.json'

def localStr(id):
	return addon.getLocalizedString(id)

def show(text):
	dialog = xbmcgui.Dialog()
	dialog.ok(localStr(32224), '%s' % (text))
	del dialog

def write(filename, text):
	with open(filename, 'w') as f:
		f.write(text)

def do_update():
	subclient = Client()

	subclient.open(py2_encode(content_settings))
	#show(subclient.content)
	sts_settings = 'Ok' if subclient.status == 200 else 'Error'
	c_s = subclient.content
	
	subclient.open(py2_encode(content_json))
	#show(subclient.content)
	sts_json = 'Ok' if subclient.status == 200 else 'Error'
	c_j = subclient.content

	if sts_json=='Ok' and sts_settings=='Ok':
		write(path_json, c_j)
		write(path_settings, c_s)
		show(localStr(32226) % (sts_settings, sts_json))
	else:
		show(localStr(32225))