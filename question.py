# [START imports]
import os
import urllib

from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.datastore.datastore_query import Cursor

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
    tags = ndb.StringProperty(repeated=True)
    
class Answer(ndb.Model):
    """Models an individual Guestbook entry with author, content, and date."""
    author = ndb.UserProperty()
    content = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)
    modifyDate = ndb.DateTimeProperty(auto_now=True)

# [START main_page]
class MainPage(webapp2.RequestHandler):

    def get(self):
        curs =Cursor(urlsafe=self.request.get('cursor'))
        
        questions_query = Question.query(
            ancestor=site_key()).order(-Question.date)
            
        if curs:
            questions, next_curs, more = questions_query.fetch_page(1, start_cursor=curs)
        else:
            questions, next_curs, more = questions_query.fetch_page(1)

        if users.get_current_user():
            signUrl = users.create_logout_url(self.request.uri)
            current_user = users.get_current_user().nickname()
        else:
            signUrl = users.create_login_url(self.request.uri)
            current_user = None

        if more and next_curs:
            query_params = {'cursor': next_curs.urlsafe()}
            nextPageUrl =  '/list?' + urllib.urlencode(query_params)
        else:
            nextPageUrl=None
        
        template_values = {
            'title': 'Question',
            'questions': questions,
            'current_user': current_user,
            'signUrl': signUrl,
            'nextPageUrl' : nextPageUrl
        }

        template = JINJA_ENVIRONMENT.get_template('mainPage.html')
        self.response.write(template.render(template_values))
# [END main_page]


class AddQuestionPage(webapp2.RequestHandler):

    # need to add tag
    def get(self):
        if users.get_current_user():
            signUrl = users.create_logout_url('/')
            current_user = users.get_current_user().nickname()
        else:
            signUrl = users.create_login_url(self.request.uri)
            self.redirect(signUrl) 
            return
        
        template_values = {
            'title': 'Add Question',
            'current_user': current_user,
            'signUrl': signUrl,
        }

        template = JINJA_ENVIRONMENT.get_template('createQuestion.html')
        self.response.write(template.render(template_values))
        

class AddQuestion(webapp2.RequestHandler):

    # need to add tag
    def post(self):
        question = Question(parent=site_key())
        if users.get_current_user():
            question.author = users.get_current_user()
        else:
            self.redirect('/') 
            return
        question.handle = self.request.get('qhandle')
        question.content = self.request.get('qcontent')
        #qcontent empty return
        question.put()
        query_params = {'qid': question.key.urlsafe()}
        question.qpermalink = '/view?' + urllib.urlencode(query_params)
        question.put()
        self.redirect('/')        

class ViewQuestion(webapp2.RequestHandler):

    #Add vote view vote handle order by vote
    def get(self):
        if users.get_current_user():
            signUrl = users.create_logout_url(self.request.uri)
            current_user = users.get_current_user().nickname()
        else:
            signUrl = users.create_login_url(self.request.uri)
            current_user = None
        
        qid = self.request.get('qid')
        if not qid:
            self.redirect('/')
            return
        
        questionKey = ndb.Key(urlsafe = qid)
        question = questionKey.get()
        
        answers = Answer.query(ancestor=questionKey).fetch()
        
        query_params = {'qid': qid}
        answerUrl = '/answer?' + urllib.urlencode(query_params)
        
        template_values = {
            'title': 'View Question',
            'current_user': current_user,
            'signUrl': signUrl,
            'question': question,
            'answers': answers,
            'answerUrl': answerUrl,
        }

        template = JINJA_ENVIRONMENT.get_template('viewQuestion.html')
        self.response.write(template.render(template_values))
        
class AnswerQuestion(webapp2.RequestHandler):

    def post(self):
        qid = self.request.get('qid')
        if not qid:
            self.redirect('/')
            return
        questionKey = ndb.Key(urlsafe = qid)
        answer = Answer(parent=questionKey)
        
        if users.get_current_user():
            answer.author = users.get_current_user()
        else:
            self.redirect('/') 
            return
        answer.content = self.request.get('acontent')
        answer.put()
        #add answer permalink
        query_params = {'qid': qid}
        questionUrl = '/view?' + urllib.urlencode(query_params)
        self.redirect(questionUrl)         


application = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/create', AddQuestionPage),
    ('/question', AddQuestion),
    ('/view', ViewQuestion),
    ('/answer', AnswerQuestion),
    ('/list', MainPage),
], debug=True)
