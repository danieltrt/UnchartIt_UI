from django.http import HttpResponse
from .src.logger import *
from .src.program import *
from .src.checker import *
from .src.interpreter import *
from .src.solver import *
from .src.model import *
from .src.distinguisher import *
from json import load
from os import listdir
import sys
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.views.generic.edit import *
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from .models import *
from .forms import *
from django.shortcuts import redirect
from django.http import JsonResponse


logger = get_logger("dist")
logger.setLevel("DEBUG")
distinguishers = {}
YESNO = "Yes/No"
OPTIONS = "Options"
f = open("./dist/example/instance1.json")
data = load(f)
f.close()


def load_dst(opt):
    # UnchartIt specific
    logger.debug("Loading programs.")
    programs = []
    programs_paths = [data['programs'] + f for f in listdir(data['programs'])]
    for program_path in programs_paths:
        programs += [UnchartItProgram(path=program_path)]

    logger.debug("Loading CBMC template.")
    template = UnchartItTemplate(data["cbmc_template"], data['input_constraints'])
    interpreter = UnchartItInterpreter(data['input_constraints'])

    # Generic
    model_checker = CBMC(template)
    solver = Solver("open-wbo")
    interaction_model = None
    if opt == YESNO: interaction_model = YesNoInteractionModel(model_checker, solver, interpreter)
    elif opt == OPTIONS: interaction_model = OptionsInteractionModel(model_checker, solver, interpreter)
    return Distinguisher(interaction_model, programs)


def yesno(request, choice_id=None, iter_n=None):
    selected_choice = None
    if iter_n is None:
        selected_choice = get_object_or_404(Choice, pk=choice_id)
        dst = distinguishers[selected_choice.question_text]
        dst.update_programs(selected_choice.correctness)
    else:
        dst = distinguishers[iter_n]

    inpt, output = dst.distinguish()
    if inpt is True and output is True:
        return render(request, 'success.html', {'program': dst.get_answer(selected_choice.correctness)})
    question = Question(id=None, question_text=inpt, interaction_model=YESNO)
    question.save()
    for out in output:
        choice = Choice(id=None, question_text=question, choice_text=out)
        choice.save()
    distinguishers[question] = dst
    return render(request, 'yesno.html', {
        'question': question, "header": inpt.get_header(), "rows": inpt.get_active_rows()
    })


def options(request, choice_id=None, iter_n=None):
    selected_choice = None
    if iter_n is None:
        selected_choice = get_object_or_404(Choice, pk=choice_id)
        dst = distinguishers[selected_choice.question_text]
        dst.update_programs(selected_choice.choice_text)
    else:
        dst = distinguishers[iter_n]

    inpt, output = dst.distinguish()
    if inpt is True and output is True:
        return render(request, 'success.html', {'program': dst.get_answer(selected_choice.choice_text)})
    question = Question(id=None, question_text=inpt, interaction_model=OPTIONS)
    question.save()
    for out in output:
        choice = Choice(id=None, question_text=question, choice_text=out)
        choice.save()
    distinguishers[question] = dst
    return render(request, 'options.html', {
        'question': question, "header": inpt.get_header(), "rows": inpt.get_active_rows()
    })


def submit(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    if question.interaction_model == OPTIONS:
        key = "choice"
        selected_choice = question.choice_set.get(pk=request.POST[key])
        selected_choice.save()
        return HttpResponseRedirect(reverse('dist:options_opt', kwargs={'choice_id': selected_choice.id}))

    elif question.interaction_model == YESNO:
        correctness = None

        if "choice_yes" in request.POST:
            key = "choice_yes"
            correctness = True
        elif "choice_no" in request.POST:
            key = "choice_no"
            correctness = False

        selected_choice = question.choice_set.get(pk=request.POST[key])
        selected_choice.correctness = correctness
        selected_choice.save()

        return HttpResponseRedirect(reverse('dist:yesno_opt', kwargs={'choice_id': selected_choice.id}))


def index(request):
    return render(request, 'home.html')


def upload(request):
    logger.debug("Loading CBMC template.")

    # build constraints list
    input_constraints = json_to_cprover(request.POST['inputConstraints'])
    constraints = [input_constraints, int(request.POST['nRows']),
                   int(request.POST['nCols']) + 1, 8, 24]
    template = UnchartItTemplate(data["cbmc_template"], constraints)
    interpreter = UnchartItInterpreter(data['input_constraints'])
    programs = []
    for file_name in list(request.FILES.keys()):
        programs += [UnchartItProgram(f=request.FILES[file_name])]

    # Generic
    model_checker = CBMC(template)
    solver = Solver("open-wbo")

    if request.POST['interactionModel'] == YESNO:
        interaction_model = YesNoInteractionModel(model_checker, solver, interpreter)
        dst = Distinguisher(interaction_model, programs)
        distinguishers[dst.n] = dst
        return HttpResponse(reverse("dist:yesno_iter", args=(0, dst.n,)))

    elif request.POST['interactionModel'] == OPTIONS:
        interaction_model = OptionsInteractionModel(model_checker, solver, interpreter)
        dst = Distinguisher(interaction_model, programs)
        distinguishers[dst.n] = dst
        return HttpResponse(reverse("dist:options_iter", args=(0, dst.n,)))

