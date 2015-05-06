from operator import or_
import re
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.http.response import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DeleteView, CreateView, UpdateView, \
    View, DetailView

from questions.forms import QuestionForm, ChoiceForm
from questions.models import Question, QuestionTag, Sentence, Word


# Create your views here.

def _get_queries(string):
    query_strings = string.split('+')
    pk_queries = []
    tag_queries = []
    for query_string in query_strings:
        if re.match("^\d+$", query_string):
            pk_queries.append(query_string)
        else:
            tag_queries.append(get_object_or_404(QuestionTag, word=query_string))
    return pk_queries, tag_queries


def _filter_questions(pk_queries, tag_queries):
    generators = []
    for pk in pk_queries:
        generators.append(Question.objects.filter(pk=pk, valid=True))
    for tag in tag_queries:
        generators.append(Question.objects.filter(tags=tag, valid=True))
    questions = reduce(or_, generators[1:], generators[0])
    return questions


def _split_text(text):
    temps = re.split("([.?])", text.rstrip())
    sentences = []
    idx = 0
    curr = ""
    while idx < len(temps):
        if re.match("^[.?]$", temps[idx]):
            curr += temps[idx][0]
            sentences.append(curr)
            curr = ""
        else:
            curr = temps[idx]
        idx += 1
    if curr != "":
        sentences.append(curr)
    return sentences


def _add_sentences(question):
    for index, text in enumerate(_split_text(question.text)):
        sentence = Sentence(question=question, text=text, index=index)
        sentence.save()


def _split_sentence(text):
    temps = re.split("(\W)", text)
    words = [temp for temp in temps if not re.match("^\s*$", temp)]
    return words


def _add_words(sentence):
    for index, text in enumerate(_split_sentence(sentence.text)):
        word = Word(sentence=sentence, text=text, index=index)
        word.save()


class QuestionListView(ListView):
    model = Question
    context_object_name = 'question_list'
    paginate_by = 20

    def get_queryset(self):
        if self.kwargs['query'] == 'all':
            return Question.objects.filter(valid=True)
        else:
            p, t = _get_queries(self.kwargs['query'])
            questions = _filter_questions(p, t)
            return questions

    def get_context_data(self, **kwargs):
        context = super(QuestionListView, self).get_context_data(**kwargs)
        return context

   
class QuestionUploadView(View):
    def post(self, request):
        form = QuestionForm(request.POST, request.FILES)
        if form.is_valid():
            # Actions
            this = form.save()

            # Add sentences
            _add_sentences(this)
            
            # Views
            if request.POST['html'] == 'false':
                return HttpResponse(str(this.pk))
            else:
                data = {'title': 'Success',
                        'message': 'Question uploaded successfully.',
                        'link': reverse('questions-list'),
                        'linkdes': 'Go to question list page.'}
                return render(request, 'result.html', data)
        else:
            # Do nothing
            
            # Views
            if request.POST['html'] == 'false':
                return HttpResponse('-1')
            else:
                data = {'title': 'Failed',
                        'message': 'Question upload failed.',
                        'link': reverse('questions-upload'),
                        'linkdes': 'Go back and upload the question again.'}
                return render(request, 'result.html', data)

    def get(self, request):
        form = QuestionForm()
        data = {'form': form, 'title':'Upload a question'}
        return  render(request, 'upload_form.html', data)

class ChoiceUploadView(View):
    def post(self, request):
        form = ChoiceForm(request.POST, request.FILES)
        print request.POST
        if form.is_valid():
            this = form.save()
            return HttpResponse(str(this.pk))
        else:
            return HttpResponse('-1')

    def get(self, request):
        form = ChoiceForm()
        return  render(request, 'upload_form.html', {'form': form, 'title': 'Upload choice'})

class QuestionDeleteView(DeleteView):
    model = Question
    # success_url = reverse_lazy('list') # Do I need this?
    slug_field = 'pk'
    
    def delete(self, request, *args, **kwargs):
        # Actions
        self.object = self.get_object()
        self.object.delete()
        
        # Views
        if 'html' in request.POST and request.POST['html'] == 'false':
            return HttpResponse('success')
        else:
            data = {'title': 'Success',
                    'message': 'Question deleted successfully.',
                    'link': reverse('questions-list'),
                    'linkdes': 'Go to question list page.',
                    }
            return render(request, 'result.html', data)
    
class QuestionDownloadView(View):
    '''
    QuestionDownloadView is similar to QuestionListView,
    except that download returns JSON while QuestionListView returns HTML.
    '''
    def get(self, request, query):
        
        if query == 'all':
            objects = Question.objects.all()
        elif re.match(r'^\d+$', query):
            objects = [Question.objects.get(pk=int(query))]
        else:
            p, t = _get_queries(query)
            objects = _filter_questions(p, t)
        data = [question.repr(request) for question in objects]
        return JsonResponse(data, safe=False)



class QuestionUpdateView(UpdateView):
    model = Question
    fields = ['text','diagram','valid','has_choices','answer','tags']
    template_name_suffix = '_update_form'
    slug_field = 'pk'
   
class QuestionUpdateAllView(View):
    '''
    This view allows user to update multiple questions at the same time
    '''
    def post(self, request):
        forms = [QuestionForm(request.POST, prefix=question.pk, instance=question)
                 for question in Question.objects.all()]
        if all([form.is_valid() for form in forms]):
            for form in forms:
                form.save()
            data = {'title': 'Success',
                    'message': 'Questions updated successfully.',
                    'link': reverse('questions-list'),
                    'linkdes': 'Go to question list page.',}
            return render(request, 'result.html', data)
        data = {'title': 'Failure',
                'message': 'Question update failed.',
                'link': reverse('questions-update_all'),
                'linkdes': 'Go back to update-all page.',}
        return render(request, 'result.html', data)
    
    def get(self, request):
        forms = [QuestionForm(prefix=question.pk, instance=question)
                 for question in Question.objects.all()]
        data = {'title':'Update questions', 'forms':forms}
        return render(request,'questions/question_update_all_form.html', data)
    
    
class QuestionDetailView(DetailView):
    
    model = Question
    context_object_name = 'question'
    slug_field = 'pk'
    
        
class TagCreateView(CreateView):
    '''
    Create a new tag
    '''
    model = QuestionTag
    fields = ['word']