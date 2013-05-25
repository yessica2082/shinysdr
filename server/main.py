#!/usr/bin/env python

from twisted.web import static, server, resource
from twisted.internet import reactor

import array # for binary stuff
import json

import sdr.top
import sdr.wfm

class GRResource(resource.Resource):
	isLeaf = True
	def __init__(self, target, field):
		'''Uses GNU Radio style accessors.'''
		self.target = target
		self.field = field
	def grrender(self, value, request):
		return str(value)
	def render_GET(self, request):
		return self.grrender(getattr(self.target, 'get_' + self.field)(), request)
	def render_PUT(self, request):
		data = request.content.read()
		getattr(self.target, 'set_' + self.field)(self.grparse(data))
		request.setResponseCode(204)
		return ''

class IntResource(GRResource):
	defaultContentType = 'text/plain'
	def grparse(self, value):
		return int(value)

class FloatResource(GRResource):
	defaultContentType = 'text/plain'
	def grparse(self, value):
		return float(value)

class SpectrumResource(GRResource):
	defaultContentType = 'application/octet-stream'
	def grrender(self, value, request):
		(freq, fftdata) = value
		# TODO: Use a more structured response rather than putting data in headers
		request.setHeader('X-SDR-Center-Frequency', str(freq))
		return array.array('f', fftdata).tostring()

class StartStop(resource.Resource):
	isLeaf = True
	def __init__(self, target, junk_field):
		self.target = target
		self.running = False
	def render_GET(self, request):
		return json.dumps(self.running)
	def render_PUT(self, request):
		value = bool(json.load(request.content))
		if value != self.running:
			self.running = value
			if value:
				self.target.start()
			else:
				self.target.stop()
				self.target.wait()
		request.setResponseCode(204)
		return ''

# Create SDR component (slow)
print 'Flow graph...'
top = sdr.top.top()
demod = top.demod

# Initialize web server first so we start accepting
print 'Web server...'
root = static.File('static/')
root.indexNames = ['index.html']
def export(block, field, ctor):
	root.putChild(field, ctor(block, field))
export(top, 'running', StartStop)
export(top, 'hw_freq', FloatResource)
export(demod, 'rec_freq', FloatResource)
export(demod, 'audio_gain', FloatResource)
export(top, 'input_rate', IntResource)
export(top, 'spectrum_fft', SpectrumResource)
reactor.listenTCP(8100, server.Site(root))

# Actually process requests.
print 'Ready.'
reactor.run()