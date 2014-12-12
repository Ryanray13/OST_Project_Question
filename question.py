# [START imports]
import os
import urllib
import datetime

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
    """Constructs a website key for All questions."""
    return ndb.Key('Site', 'site')

class Vote(ndb.Model):
    """Models an individual Vote entry """
    author = ndb.UserProperty()
    value = ndb.StringProperty(indexed=False)
    createTime = ndb.DateTimeProperty(auto_now_add=True)
    modifyTime = ndb.DateTimeProperty(auto_now=True)
    voteType = ndb.BooleanProperty()
    
class Question(ndb.Model):
    """Models an individual Question entry """
    author = ndb.UserProperty()
    content = ndb.StringProperty(indexed=False)
    createTime = ndb.DateTimeProperty(auto_now_add=True)
    handle = ndb.StringProperty(indexed=False)
    modifyTime = ndb.DateTimeProperty()
    tags = ndb.StringProperty(repeated=True)
    voteResult = ndb.IntegerProperty()
    
class Answer(ndb.Model):
    """Models an individual Answer entry """
    author = ndb.UserProperty()
    content = ndb.StringProperty(indexed=False)
    createTime = ndb.DateTimeProperty(auto_now_add=True)
    modifyTime = ndb.DateTimeProperty()
    voteResult = ndb.IntegerProperty()

# [START main_page]
class MainPage(webapp2.RequestHandler):

    def get(self):
        try:
            curs =Cursor(urlsafe=self.request.get('cursor'))
        except:
            self.redirect('/')
            return
        questions_query = Question.query(
            ancestor=site_key()).order(-Question.modifyTime)
            
        if curs:
            questions, next_curs, more = questions_query.fetch_page(1, start_cursor=curs)
        else:
            questions, next_curs, more = questions_query.fetch_page(1)

        if users.get_current_user():
            signUrl = users.create_logout_url(self.request.uri)
            current_user = users.get_current_user()
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
    #render create question page and edit question page
    # need to add tag
    def get(self):
        if users.get_current_user():
            signUrl = users.create_logout_url('/')
            current_user = users.get_current_user()
        else:
            signUrl = users.create_login_url('/')
            self.redirect(signUrl) 
            return
        
        if self.request.get('qid'):
            qid = self.request.get('qid')
            try:
                questionKey = ndb.Key(urlsafe = qid)
            except:
                self.redirect('/')
                return
            question = questionKey.get()
        else:
            question=None
            
        template_values = {
            'title': 'Add Question',
            'current_user': current_user,
            'signUrl': signUrl,
            'question':question
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
            signUrl = users.create_login_url('/')
            self.redirect(signUrl) 
            return
        question.handle = self.request.get('qhandle')
        question.content = self.request.get('qcontent')
        if not question.content:
            self.response.write('<script type="text/javascript">alert(" Question cannot be Empty ! ");\
                                 window.location.href="%s"</script>' %('/create'))
            return
        question.voteResult = 0
        question.modifyTime = datetime.datetime.now()
        qkey = question.put()
        query_params = {'qid': qkey.urlsafe()}
        questionUrl = '/view?' + urllib.urlencode(query_params)
        self.redirect(questionUrl)   
      
class EditQuestion(webapp2.RequestHandler):

    def post(self):
        if users.get_current_user():
            author = users.get_current_user()
        else:
            signUrl = users.create_login_url('/')
            self.redirect(signUrl) 
            return
        
        if self.request.get('qid'):
            qid = self.request.get('qid')
        else:
            self.redirect('/')
            return
        try:
            questionKey = ndb.Key(urlsafe=qid)
        except:
            self.redirect('/')
            return
        question = questionKey.get()
        if question.author != author:
            self.redirect('/')
            return
        question.handle = self.request.get('qhandle')
        query_params = {'qid': qid}
        questionEditUrl = '/create?' + urllib.urlencode(query_params)
        if not self.request.get('qcontent'):
            self.response.write('<script type="text/javascript">alert(" Question cannot be Empty ! ");\
                                 window.location.href="%s"</script>' %(questionEditUrl))
            return
        question.content = self.request.get('qcontent')
        question.modifyTime = datetime.datetime.now()
        qkey = question.put()
        query_params = {'qid': qkey.urlsafe()}
        questionUrl = '/view?' + urllib.urlencode(query_params)
        self.redirect(questionUrl)                 

class ViewQuestion(webapp2.RequestHandler):

    #Add vote view vote handle order by vote
    def get(self):
        if users.get_current_user():
            signUrl = users.create_logout_url(self.request.uri)
            current_user = users.get_current_user()
        else:
            signUrl = users.create_login_url(self.request.uri)
            current_user = None
       
        if self.request.get('qid'):
            qid = self.request.get('qid')
            try:
                questionKey = ndb.Key(urlsafe = qid)
            except:
                self.redirect('/')
                return
            question = questionKey.get()       
            answers = Answer.query(ancestor=questionKey).order(-Answer.voteResult).fetch()
            edit = False
            query_params = {'qid': qid}
            answerUrl = '/answer?' + urllib.urlencode(query_params)
        elif self.request.get('aid') :
            aid = self.request.get('aid')
            try:
                answerKey = ndb.Key(urlsafe = aid)
            except:
                self.redirect('/')
                return
            questionKey = answerKey.parent()
            qid = questionKey.urlsafe()
            question = questionKey.get()
            answers = answerKey.get()
            edit = True
            query_params = {'aid': aid}
            answerUrl = '/edita?' + urllib.urlencode(query_params)
        else:
            self.redirect('/')
            return
        
        template_values = {
            'title': 'View Question',
            'current_user': current_user,
            'signUrl': signUrl,
            'question': question,
            'answers': answers,
            'answerUrl': answerUrl,
            'edit':edit
        }

        template = JINJA_ENVIRONMENT.get_template('viewQuestion.html')
        self.response.write(template.render(template_values))
       
class AnswerQuestion(webapp2.RequestHandler):

    def post(self):       
        if not users.get_current_user():
            signUrl = users.create_login_url('/')
            self.redirect(signUrl) 
            return
        qid = self.request.get('qid')
        if not qid:
            self.redirect('/')
            return
        try:
            questionKey = ndb.Key(urlsafe = qid)
        except:
            self.redirect('/')
            return
        answer = Answer(parent=questionKey)
        query_params = {'qid': qid}
        questionUrl = '/view?' + urllib.urlencode(query_params)
        answer.author = users.get_current_user()
        answer.content = self.request.get('acontent')
        if not answer.content:
            self.response.write('<script type="text/javascript">alert(" Answer cannot be Empty ! ");\
                                 window.location.href="%s"</script>' %(questionUrl))
            return
        answer.voteResult = 0
        answer.modifyTime = datetime.datetime.now()
        answer.put()
        self.redirect(questionUrl)    

class EditAnswer(webapp2.RequestHandler):

    def post(self):
        if users.get_current_user():
            author = users.get_current_user()
        else:
            signUrl = users.create_login_url('/')
            self.redirect(signUrl) 
            return
          
        if self.request.get('aid'):
            aid = self.request.get('aid')
        else:
            self.redirect('/')
            return    
            
        try:
            answerKey = ndb.Key(urlsafe=aid)
        except:
            self.redirect('/')
            return
        
        answer = answerKey.get()
        if answer.author != author:
            self.redirect('/')
            return
        qid = answerKey.parent().urlsafe()
        query_params = {'qid':qid}
        questionUrl = '/view?' + urllib.urlencode(query_params)        
        if not self.request.get('acontent'):
            self.response.write('<script type="text/javascript">alert(" Answer cannot be Empty ! ");\
                                 window.location.href="%s"</script>' %(questionUrl))
            return
        answer.content = self.request.get('acontent')
        answer.modifyTime = datetime.datetime.now()
        answer.put()
        self.redirect(questionUrl) 
        
class AddVote(webapp2.RequestHandler):

    def post(self):
        if self.request.get('qid') and self.request.get('value'):                
            qid = self.request.get('qid')
            try:
                questionKey = ndb.Key(urlsafe = qid)
            except:
                self.redirect('/')
                return
            query_params = {'qid': qid}
            questionUrl = '/view?' + urllib.urlencode(query_params)
            if self.request.get('value') == 'Up' or self.request.get('value') == 'Down':
                value = self.request.get('value')
            else:
                self.redirect(questionUrl) 
                return
                
            if not users.get_current_user():
                signUrl = users.create_login_url(questionUrl)
                self.redirect(signUrl) 
                return
            
            current_user = users.get_current_user()
            
            if self.request.get('aid'):
                aid = self.request.get('aid')
                try:
                    answerKey = ndb.Key(urlsafe = aid)
                except:
                    self.redirect(questionUrl)
                    return
                answer = answerKey.get();
                votes = Vote.query(ancestor=answerKey).fetch()

                voteFound = False
                for vote in votes:
                    if vote.author == current_user:
                        voteFound=True
                        if value == vote.value:
                            self.response.write('<script type="text/javascript">alert(" You already voted ! ");\
                                 window.location.href="%s"</script>' %(questionUrl))
                            return
                        else:
                            if vote.value == 'none':
                                vote.value = value
                            else:
                                vote.value = 'none'
                            vote.put()
                        break
                
                if not voteFound:
                    newVote = Vote(parent=answerKey)
                    newVote.value = value
                    newVote.author = current_user
                    newVote.voteType = False
                    newVote.put()
                if value == 'Up':       
                    answer.voteResult = answer.voteResult + 1
                else:
                    answer.voteResult = answer.voteResult - 1
                answer.put()
                             
            else:
                question = questionKey.get()
                votes = Vote.query(ancestor=questionKey).filter(Vote.voteType==True).fetch()
                voteFound = False
                for vote in votes:
                    if vote.author == current_user:
                        voteFound=True
                        if value == vote.value:
                            self.response.write('<script type="text/javascript">alert(" You already voted ! ");\
                                 window.location.href="%s"</script>' %(questionUrl))
                            return
                        else:
                            if vote.value == 'none':
                                vote.value = value
                            else:
                                vote.value = 'none'
                            vote.put()
                        break
                
                if not voteFound:
                    newVote = Vote(parent=questionKey)
                    newVote.value = value
                    newVote.author = current_user
                    newVote.voteType = True
                    newVote.put()
                if value == 'Up':       
                    question.voteResult = question.voteResult + 1
                else:
                    question.voteResult = question.voteResult - 1
                question.put()
            self.redirect(questionUrl)      
        else:
            self.redirect('/')
            return             


application = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/create', AddQuestionPage),
    ('/question', AddQuestion),
    ('/view', ViewQuestion),
    ('/answer', AnswerQuestion),
    ('/list', MainPage),
    ('/vote', AddVote),
    ('/editq', EditQuestion),
    ('/edita', EditAnswer),
], debug=True)
