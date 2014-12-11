# [START imports]
import os
import urllib

from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
# [END imports]

DEFAULT_USER_NAME = 'anonymous'


# We set a parent key on the 'Questions' to ensure that they are all in the same
# entity group. Queries across the single entity group will be consistent.
# However, the write rate should be limited to ~1/second.

def site_key():
    """Constructs a Datastore key for a User entity with current_user."""
    return ndb.Key('Site', 'site')

class Vote(ndb.Model):
    """Models an individual Guestbook entry with author, content, and date."""
    author = ndb.UserProperty()
    content = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)    

class Question(ndb.Model):
    """Models an individual Guestbook entry with author, content, and date."""
    author = ndb.UserProperty()
    content = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)
    handle = ndb.StringProperty(indexed=False)
    modifyDate = ndb.DateTimeProperty(auto_now=True)
    qpermalink = ndb.StringProperty(indexed=False)
    qvotes = ndb.StructuredProperty(Vote,repeated=True)
    
class Answer(ndb.Model):
    """Models an individual Guestbook entry with author, content, and date."""
    author = ndb.UserProperty()
    content = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)

# [START main_page]
class MainPage(webapp2.RequestHandler):

    def get(self):
        page =self.request.get('page',1)
        
        questions_query = Question.query(
            ancestor=site_key()).order(-Question.date)
        if page != 1:
            questions_query.fetch((page-1)*10)
        questions = questions_query.fetch(10)

        if users.get_current_user():
            url = users.create_logout_url(self.request.uri)
            current_user = users.get_current_user().nickname()
            url_linktext = 'Logout ' + current_user
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
            current_user = None

        template_values = {
            'title': 'Question',
            'questions': questions,
            'current_user': current_user,
            'url': url,
            'url_linktext': url_linktext,
        }

        template = JINJA_ENVIRONMENT.get_template('mainPage.html')
        self.response.write(template.render(template_values))
# [END main_page]


class CreateQuestion(webapp2.RequestHandler):

    def post(self):
        question = Question(parent=site_key())
        if users.get_current_user():
            question.author = users.get_current_user()
        question.handle = self.request.get('qhandle')
        question.content = self.request.get('qcontent')
        question.put()
        query_params = {'qid': question.key.urlsafe()}
        question.qpermalink = '/view?' + urllib.urlencode(query_params)
        question.put()
        self.redirect('/')


application = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/create', CreateQuestion),
    ('/view', MainPage),
    ('/answer', MainPage),
    ('/list', MainPage),
], debug=True)
