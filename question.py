# [START imports]
import os
import urllib
import datetime
import re

from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.ext import blobstore
from google.appengine.datastore.datastore_query import Cursor
from google.appengine.ext.webapp import blobstore_handlers

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

#Custom jinja2 regex replacement filter
def replacelink(s):
    """a regex link convert filter"""
    def replink(m):
        imageString = 'http://' + os.environ['HTTP_HOST'] + '/img'
        if m.group().endswith('.jpg') or m.group().endswith('.png') or m.group().endswith('.gif'):
            return  '<img src="'  + m.group() + '">'
        elif m.group().startswith(imageString):
            return  '<img src="'  + m.group() + '">'
        else:
            return '<a href="' + m.group(1) + '">' + m.group(2) + '</a>'
    return re.sub(r'(https?://([^ ,;\n]*))', replink, s)

#replace link for mainpage, mainly just resize the image
def replacelinkSmall(s):
    """a regex link convert filter"""
    def replink(m):
        imageString = 'http://' + os.environ['HTTP_HOST'] + '/img'
        if m.group().endswith('.jpg') or m.group().endswith('.png') or m.group().endswith('.gif'):
            return  '<img src="'  + m.group() + '" height="50" width="50">' 
        elif m.group().startswith(imageString):
            return  '<img src="'  + m.group() + '" height="50" width="50">' 
        else:
            return '<a href="' + m.group(1) + '">' + m.group(2) + '</a>'
    return re.sub(r'(https?://([^ ,;\n]*))', replink, s)

#Custom jinja2 quote filter
def urlquote(s):
    """a regex quote filter"""
    return urllib.quote(s)

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
    voteResult = ndb.IntegerProperty() #separate field store up-down vote number
    
class Answer(ndb.Model):
    """Models an individual Answer entry """
    author = ndb.UserProperty()
    content = ndb.StringProperty(indexed=False)
    createTime = ndb.DateTimeProperty(auto_now_add=True)
    modifyTime = ndb.DateTimeProperty()
    voteResult = ndb.IntegerProperty() #separate field store up-down vote number

# [START main_page]
class MainPage(webapp2.RequestHandler):
    """ mainpage to show all questions or qustions by tag  """
    def get(self):
        # if there is a tag, get questions by tag
        if self.request.get('tag'):
            tag = self.request.get('tag')
            questions_query = Question.query(
            ancestor=site_key()).filter(Question.tags == tag).order(-Question.modifyTime)
        else:
            questions_query = Question.query(
            ancestor=site_key()).order(-Question.modifyTime)
        
        #check whether cursor exists
        if self.request.get('cursor'):
            try:
                curs =Cursor(urlsafe=self.request.get('cursor'))
            except:
                self.redirect('/')
                return          
            questions, next_curs, more = questions_query.fetch_page(10, start_cursor=curs)

        else:
            questions, next_curs, more = questions_query.fetch_page(10)

        if users.get_current_user():
            signUrl = users.create_logout_url(self.request.uri)
            current_user = users.get_current_user()
        else:
            signUrl = users.create_login_url(self.request.uri)
            current_user = None

        if more and next_curs:
            if self.request.get('tag'):
                query_params = {'cursor': next_curs.urlsafe(),'tag':self.request.get('tag')}
            else:
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

        #using customer filter to convert link
        JINJA_ENVIRONMENT.filters['replink'] = replacelinkSmall
        template = JINJA_ENVIRONMENT.get_template('mainPage.html')
        self.response.write(template.render(template_values))
# [END main_page]

class GetTagsPage(webapp2.RequestHandler):
    """  This is a page show all the tags """
    def get(self):
        if users.get_current_user():
            signUrl = users.create_logout_url(self.request.uri)
            current_user = users.get_current_user()
        else:
            signUrl = users.create_login_url(self.request.uri)
            current_user = None
        questions = Question.query(ancestor=site_key()).fetch()
        tagsUrl={}
        for question in questions:
            for tag in question.tags:
                if tag not in tagsUrl:
                    query_params = {'tag': tag}
                    tagsUrl[tag] = ('/list?' + urllib.urlencode(query_params))
        template_values = {
            'title':'Tags',
            'tagsUrl':tagsUrl,
            'current_user': current_user,
            'signUrl': signUrl,
        }

        template = JINJA_ENVIRONMENT.get_template('tags.html')
        self.response.write(template.render(template_values))
     
class AddQuestionPage(webapp2.RequestHandler):
    """ "render create question page and edit question page """

    def get(self):
        if users.get_current_user():
            signUrl = users.create_logout_url('/')
            current_user = users.get_current_user()
        else:
            signUrl = users.create_login_url('/')
            self.redirect(signUrl) 
            return
        
        #if there is qid, indicates this is editing, load the question
        if self.request.get('qid'):
            qid = self.request.get('qid')
            try:
                questionKey = ndb.Key(urlsafe = qid)
            except:
                self.redirect('/')
                return
            question = questionKey.get()
            title = 'Edit Quetsion'
            upload_url = blobstore.create_upload_url('/editq?qid=' + question.key.urlsafe())
        else:
            question=None
            title = 'Create Question'
            upload_url = blobstore.create_upload_url('/question')
               
        template_values = {
            'title': title,
            'current_user': current_user,
            'signUrl': signUrl,
            'question':question,
            'uploadUrl' : upload_url
        }

        template = JINJA_ENVIRONMENT.get_template('createQuestion.html')
        self.response.write(template.render(template_values))
        

class AddQuestion(blobstore_handlers.BlobstoreUploadHandler):
    """  handler to handle adding question """

    def post(self):
        question = Question(parent=site_key())
        if users.get_current_user():
            question.author = users.get_current_user()
        else:
            signUrl = users.create_login_url('/')
            self.redirect(signUrl) 
            return
        question.handle = self.request.get('qhandle')      
        qtags = self.request.get('tag')
        #insure the tags doesn't repeat
        question.tags = set(qtags.split())
        #if content is empty, pop out error window.
        if not self.request.get('qcontent'):
            self.response.write('<script type="text/javascript">alert(" Question cannot be Empty ! ");\
                                 window.location.href="%s"</script>' %('/create'))
            return
        question.content = self.request.get('qcontent')
        question.voteResult = 0
        upload_images = self.get_uploads('image')
        if upload_images:
            for image in upload_images:
                blob_info = image
                question.content += ' http://' + os.environ['HTTP_HOST'] + ('/img/%s' % blob_info.key()) + ' '
        question.content = re.sub('(\n)+','',question.content)    
        question.handle = re.sub('(\r\n)+','',question.handle)   
        question.modifyTime = datetime.datetime.now()
        qkey = question.put()
        query_params = {'qid': qkey.urlsafe()}
        questionUrl = '/view?' + urllib.urlencode(query_params)
        self.redirect(questionUrl)   
      
class EditQuestion(blobstore_handlers.BlobstoreUploadHandler):
    """ This is the handler for editing question """
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
        question.tags =  set(self.request.get('tag').split())
        #change the modify time
        upload_images = self.get_uploads('image')
        if upload_images:
            for image in upload_images:
                blob_info = image
                question.content += ' http://' + os.environ['HTTP_HOST'] + ('/img/%s' % blob_info.key()) + ' '
        question.handle = re.sub('(\r\n)+','',question.handle) 
        question.content = re.sub('(\r\n)+','',question.content) 
        question.modifyTime = datetime.datetime.now()
        qkey = question.put()
        query_params = {'qid': qkey.urlsafe()}
        questionUrl = '/view?' + urllib.urlencode(query_params)
        self.redirect(questionUrl)                 

class ViewQuestion(webapp2.RequestHandler):
    """ render view question page """
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
            upload_url = blobstore.create_upload_url(answerUrl)
            #upload_url = answerUrl
            title='View Question'
        elif self.request.get('aid'):
            # if there is aid, then is editing that answer, show that answer only
            aid = self.request.get('aid')
            try:
                answerKey = ndb.Key(urlsafe = aid)
            except:
                self.redirect('/')
                return
            questionKey = answerKey.parent()
            question = questionKey.get()
            answers = answerKey.get()
            edit = True
            query_params = {'aid': aid}
            answerUrl = '/edita?' + urllib.urlencode(query_params)
            upload_url = blobstore.create_upload_url(answerUrl)
            #upload_url = answerUrl
            title='Edit Answer'
        else:
            self.redirect('/')
            return
        
        template_values = {
            'title': title,
            'current_user': current_user,
            'signUrl': signUrl,
            'question': question,
            'answers': answers,
            'uploadUrl': upload_url,
            'edit':edit,
        }
        JINJA_ENVIRONMENT.filters['replink'] = replacelink
        JINJA_ENVIRONMENT.filters['urlquote'] = urlquote
        template = JINJA_ENVIRONMENT.get_template('viewQuestion.html')
        self.response.write(template.render(template_values))
       
class AnswerQuestion(blobstore_handlers.BlobstoreUploadHandler):
    """ handler for adding answers """
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
        if not self.request.get('acontent'):
            self.response.write('<script type="text/javascript">alert(" Answer cannot be Empty ! ");\
                                 window.location.href="%s"</script>' %(questionUrl))
            return
        answer.content = self.request.get('acontent')
        upload_images = self.get_uploads('image')
        if upload_images:
            for image in upload_images:
                blob_info = image
                answer.content += ' http://' + os.environ['HTTP_HOST'] + ('/img/%s' % blob_info.key()) + ' '
        answer.content = re.sub('(\r\n)+','',answer.content) 
        answer.voteResult = 0
        answer.modifyTime = datetime.datetime.now()
        answer.put()
        self.redirect(questionUrl)    

class EditAnswer(blobstore_handlers.BlobstoreUploadHandler):
    """ handler for editing answer """
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
        upload_images = self.get_uploads('image')
        if upload_images:
            for image in upload_images:
                blob_info = image
                answer.content += ' http://' + os.environ['HTTP_HOST'] + ('/img/%s' % blob_info.key()) + ' '
        answer.content = re.sub('(\r\n)+','',answer.content)
        answer.modifyTime = datetime.datetime.now()
        answer.put()
        self.redirect(questionUrl) 
        
class AddVote(webapp2.RequestHandler):
    """ handler for voting """
    def post(self):
        if (self.request.get('qid') or self.request.get('aid')) and self.request.get('value'):
            if self.request.get('qid'):
                qid = self.request.get('qid')
                try:
                    questionKey = ndb.Key(urlsafe = qid)
                except:
                    self.redirect('/')
                    return
                query_params = {'qid': qid}
                questionUrl = '/view?' + urllib.urlencode(query_params)
            
            if self.request.get('aid'):
                aid = self.request.get('aid')    
                try:
                    answerKey = ndb.Key(urlsafe = aid)
                except:
                    if self.request.get('qid'):
                        self.redirect(questionUrl)
                    else:
                        self.redirect('/')
                    return
                if not self.request.get('qid'):
                    qid = answerKey.parent().urlsafe()
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

class RssPage(webapp2.RequestHandler):
    """ render rss page """
    def get(self):
        if self.request.get('qid'):
            qid = self.request.get('qid')
            try:
                questionKey = ndb.Key(urlsafe = qid)
            except:
                self.redirect('/')
                return
            question = questionKey.get()
            title = 'Question Rss'
            chanelLink='http://' + os.environ['HTTP_HOST'] +'/view?qid=' +questionKey.urlsafe()
            chanelDes = 'Feed for single question with its answers'
            questionLink = {}
            questionLink[questionKey.id()]=chanelLink
            answers=Answer.query(ancestor=questionKey).order(-Answer.voteResult).fetch()
            questions=None
        else:
            title = 'Mainpage Rss'
            questions = Question.query(ancestor=site_key()).order(-Question.modifyTime).fetch()
            chanelLink=self.request.uri
            chanelDes = 'Feed for all questions'
            answers = None
            questionLink={}
            for question in questions:
                questionLink[question.key.id()] = 'http://' + os.environ['HTTP_HOST'] + '/view?qid=' +question.key.urlsafe()
            question = None
            
        template_values = {
            'title': title,
            'chanelLink': chanelLink,
            'chanelDes' : chanelDes,
            'questions':questions,
            'question' : question,
            'answers' : answers,
            'questionLink': questionLink
        }

        self.response.headers['Content-Type'] = 'application/rss+xml;charset=utf-8'
        template = JINJA_ENVIRONMENT.get_template('questionRss.xml')
        self.response.write(template.render(template_values))

class ImageHandler(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, resource):
        resource = str(urllib.unquote(resource))
        blob_info = blobstore.BlobInfo.get(resource)
        self.send_blob(blob_info)
    
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
    ('/tags', GetTagsPage),
    ('/rss', RssPage),
    ('/img/([^/]+)?', ImageHandler)
], debug=True)
