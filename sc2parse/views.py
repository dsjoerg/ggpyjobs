import sys, traceback

from django.shortcuts import render_to_response
from django.template import RequestContext

def helloworld(request):
    return render_to_response('hi.html', context_instance = RequestContext(request))

