from urllib.parse import parse_qs
from django.db.models import F
from django.utils.dateparse import parse_date
from django.views import View
from django.template import loader
from django.urls import reverse_lazy
from django.forms import formset_factory
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404, redirect
from django.core.serializers.json import DjangoJSONEncoder
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.db import transaction
from easyaudit.models import CRUDEvent

from ..caf.ColdForensic import ColdForensic
from .models import Case, User, Evidence, Acquisition, PhysicalAcquisition, SelectiveFullFileSystemAcquisition
from .forms import CaseUpdateForm, EvidenceUpdateForm, ChainOfCustodyForm, AdditionalInfoForm
from apps.home.asynchronous.task import physicalAcquisition, selectiveFfsAcquisition
import random, string, json, uuid
from datetime import datetime
from pathlib import Path


class UUIDEncoder(DjangoJSONEncoder):
    """
    Class: UUIDEncoder

    Inherits: DjangoJSONEncoder

    Description:
    This class is responsible for encoding UUID objects into JSON serializable format by extending the DjangoJSONEncoder class.

    Methods:
    1. default(self, obj)
        - Description: This method overrides the default method of DjangoJSONEncoder class to encode UUID objects.
        - Parameter:
            - obj: The object to be encoded into JSON serializable format.
        - Returns:
            - If the object is an instance of UUID, it returns the string representation of the UUID.
            - Otherwise, it calls the default method of the parent class to handle the encoding.

    """
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


class Dashboard(View):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):

        totalInvestigator = User.objects.filter(user_roles='Investigator').count()
        totalCases = Case.objects.count()
        totalEvidences = Evidence.objects.count()

        context = {
            'totalInvestigator': totalInvestigator,
            'totalCases': totalCases,
            'totalEvidences': totalEvidences,
        }
        html_template = loader.get_template('home/index.html')
        return HttpResponse(html_template.render(context, request))


class CaseListView(ListView):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    model = Case
    fields = '__all__'
    template_name = 'home/case.html'
    success_url = reverse_lazy('cases_home:all')

    # if want to show all cases, including the soft-deleted ones, use the following code
    # def get_queryset(self):
    #     return Case.all_objects.all()


class CaseCreateView(CreateView):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    model = Case
    template_name = 'home/case_create.html'
    fields = ['case_number', 'description', 'case_name', 'case_is_open', 'case_member']

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        self.object.case_member.add(self.request.user.id)
        self.object.case_member.add(*self.request.POST.getlist('case_member'))

        additional_info = {}
        additional_info.update({
            'addinfo_name': self.request.POST.get('addinfo_name'),
            'addinfo_agency': self.request.POST.get('addinfo_agency'),
            'addinfo_phone': self.request.POST.get('addinfo_phone'),
            'addinfo_fax': self.request.POST.get('addinfo_fax'),
            'addinfo_address': self.request.POST.get('addinfo_address'),
            'addinfo_email': self.request.POST.get('addinfo_email'),
            'addinfo_notes': self.request.POST.get('addinfo_notes'),
        })

        self.object.additional_info = additional_info
        self.object.save()
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['home_user_list'] = User.objects.exclude(id=self.request.user.id)
        return context

    def get_success_url(self):
        return reverse_lazy('cases_home')


class CaseUpdateView(UpdateView):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    model = Case
    template_name = 'home/case_update.html'
    form_class = CaseUpdateForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Check if additional_info exists
        has_additional_info = bool(self.object.additional_info)

        if has_additional_info:
            extra = 0
            if isinstance(self.object.additional_info, list):
                initial_data = self.object.additional_info
            else:
                initial_data = [self.object.additional_info]
        else:
            extra = 1  # Provide one empty form when no additional_info exists
            initial_data = []

        # Create the formset with the determined 'extra' value
        AdditionalInfoFormSet = formset_factory(AdditionalInfoForm, extra=extra)

        if self.request.method == 'POST':
            context['additional_info_formset'] = AdditionalInfoFormSet(self.request.POST)
        else:
            context['additional_info_formset'] = AdditionalInfoFormSet(initial=initial_data)

        return context

    def get_success_url(self):
        return reverse_lazy('cases_home')

    def get_object(self, queryset=None):
        case_id = self.kwargs['case_id']
        return get_object_or_404(Case, case_id=case_id)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_user'] = self.request.user  # Pass current user to the form
        return kwargs

    def form_valid(self, form):
        context = self.get_context_data()
        additional_info_formset = context['additional_info_formset']

        if additional_info_formset.is_valid():
            response = super().form_valid(form)
            case = self.object

            # Get selected members from the form
            selected_members = form.cleaned_data['case_member']

            # Ensure the creator is included in the case members
            selected_members = list(selected_members)  # Convert to list to allow modification
            if case.user.id not in selected_members:
                selected_members.append(self.request.user)

            # Update the case members
            case.case_member.set(selected_members)

            additional_info = {}
            for form in additional_info_formset.cleaned_data:
                if not form.get('DELETE', False):
                    additional_info.update({
                        'addinfo_name': form.get('addinfo_name'),
                        'addinfo_agency': form.get('addinfo_agency'),
                        'addinfo_phone': form.get('addinfo_phone'),
                        'addinfo_fax': form.get('addinfo_fax'),
                        'addinfo_address': form.get('addinfo_address'),
                        'addinfo_email': form.get('addinfo_email'),
                        'addinfo_notes': form.get('addinfo_notes'),
                    })

            self.object.additional_info = additional_info
            self.object.save()
            return response
        else:
            return super().form_invalid(form)


@method_decorator(csrf_exempt, name='dispatch')
class CaseDeleteView(View):
    def post(self, request, *args, **kwargs):
        case_id = self.kwargs.get('case_id')
        case = get_object_or_404(Case, case_id=case_id)

        # Perform soft delete
        case.is_deleted = True
        case.save()

        return JsonResponse({'success': True})

    def get_success_url(self):
        return reverse_lazy('cases_home')


def is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def activitiesList(request):
    # event_type from query
    event_type = request.GET.get('event_type')
    # date range from query
    start_date_str = request.GET.get('start')
    end_date_str = request.GET.get('end')

    # Base QuerySet (UNSLICED)
    all_events = CRUDEvent.objects.all().order_by('-datetime')

    # 1) Filter by event type, if any
    if event_type:
        try:
            etype_val = int(event_type)
            all_events = all_events.filter(event_type=etype_val)
        except ValueError:
            pass

    # 2) Filter by date range, if given
    if start_date_str and end_date_str:
        start_date = parse_date(start_date_str)
        end_date = parse_date(end_date_str)
        if start_date and end_date:
            all_events = all_events.filter(datetime__date__range=(start_date, end_date))

    # 3) Now slice for your initial load
    all_events = all_events[:25]

    context = {
        'events': all_events,
        'event_type': event_type,
        'start_date': start_date_str,
        'end_date': end_date_str,
    }
    return render(request, 'home/activities.html', context)



def activitiesAjax(request):
    """
    Handles AJAX requests for the next batch of events.
    Returns JSON, which the front end will use to append to the table.
    """
    offset = int(request.GET.get('offset', 0))
    limit = int(request.GET.get('limit', 15))
    event_type = request.GET.get('event_type')
    start_date_str = request.GET.get('start')
    end_date_str = request.GET.get('end')

    all_events = CRUDEvent.objects.all().order_by('-datetime')

    # 1) Filter by event type
    if event_type:
        try:
            etype_val = int(event_type)
            all_events = all_events.filter(event_type=etype_val)
        except ValueError:
            pass

    # 2) Filter by date range
    if start_date_str and end_date_str:
        start_date = parse_date(start_date_str)
        end_date = parse_date(end_date_str)
        if start_date and end_date:
            all_events = all_events.filter(datetime__date__range=(start_date, end_date))

    # 3) Now slice for lazy loading
    events_slice = all_events[offset: offset + limit]

    # Convert the events to a JSON-serializable structure
    data = []
    for e in events_slice:
        if e.is_create():
            event_label = "Create"
        elif e.is_update():
            event_label = "Update"
        elif e.is_delete():
            event_label = "Delete"
        else:
            event_label = "Other"

        data.append({
            'datetime': e.datetime.strftime("%d %b %Y, %I:%M %p"),
            'user': str(e.user) if e.user else "—",
            'event_type': event_label,
            'object_repr': e.object_repr,
            'changed_fields': e.changed_fields,
        })

    return JsonResponse({'events': data})

def get_case_members_by_evidence(request, evidence_id):
    evidence = get_object_or_404(Evidence, evidence_id=evidence_id)
    members = evidence.case.case_member.all().values('id', 'user_name', 'user_roles')
    return JsonResponse(list(members), safe=False)

def get_case_members(request, case_id):
    case = get_object_or_404(Case, case_id=case_id)
    members = case.case_member.all().values('id', 'user_name', 'user_roles')
    return JsonResponse(list(members), safe=False)

def get_evidence_coc(request, evidence_id):
    offset = int(request.GET.get('offset', 0))
    limit = int(request.GET.get('limit', 10))

    evidence = Evidence.objects.get(evidence_id=evidence_id)
    chain_of_custody_data = evidence.evidence_chain_of_custody

    # Since chain_of_custody_data is already a list, use it directly
    if isinstance(chain_of_custody_data, list):
        chain_of_custody_list = chain_of_custody_data
    else:
        # Handle the case where it's a string (if necessary)
        try:
            chain_of_custody_list = json.loads(chain_of_custody_data)
        except (json.JSONDecodeError, TypeError):
            chain_of_custody_list = []

    coc_count = len(chain_of_custody_list)
    chain_of_custody = chain_of_custody_list[offset:offset + limit]

    if is_ajax(request) and request.GET.get('isLoaded') != 'true':
        context = {
            'chain_of_custody': chain_of_custody,
            'evidence': evidence,
            'coc_count': coc_count
        }
        return render(request, 'includes/evidence_coc_activities.html', context)
    elif request.GET.get('isLoaded') == 'true':
        context = {
            'evidence': evidence,
            'chain_of_custody': chain_of_custody,
            'coc_count': coc_count,
        }
        return render(request, 'includes/evidence_coc.html', context)

def get_evidence_acquisition_history(request, evidence_id):
    offset = int(request.GET.get('offset', 0))
    limit = int(request.GET.get('limit', 10))

    acquisition_qs = Acquisition.objects.filter(evidence=evidence_id).order_by('date')
    acquisition_count = acquisition_qs.count()
    acquisition = acquisition_qs[offset:offset + limit]
    evidence = Evidence.objects.get(evidence_id=evidence_id)

    if is_ajax(request) and request.GET.get('isLoaded') != 'true':
        # Return partial HTML for AJAX requests
        print(f'Original {acquisition_count} acquisition records')
        context = {'acquisition': acquisition, 'evidence': evidence, 'acquisition_count': acquisition_count}
        return render(request, 'includes/acquisition_activities.html', context)
    elif request.GET.get('isLoaded') == 'true':
        print(f'Loaded {acquisition_count} acquisition records')
        # Render full modal for initial load
        context = {
            'acquisition': acquisition,
            'evidence': evidence,
            'acquisition_count': acquisition_count,
        }
        return render(request, 'includes/evidence_acquisition_history.html', context)

def start_acquisition_task(unique_link):
    acquisitionObject = Acquisition.objects.get(unique_link=unique_link)

    # Ensure necessary data is present before starting the task
    if not acquisitionObject.full_path and acquisitionObject.file_name:
        # Handle the error or wait until data is available
        print("Data not ready for acquisition")
        return

    if acquisitionObject.status in ["failed", "cancelled"]:
        # Resume the failed acquisition
        acquisitionObject.status = "in_progress"
        acquisitionObject.save()

    if acquisitionObject.acquisition_type == "physical":
        result = physicalAcquisition.delay('acquisition-progress_%s' % unique_link, unique_link)
        print("Task started with status ->", result.status)
    elif acquisitionObject.acquisition_type == "selective_full_file_system":
        result = selectiveFfsAcquisition.delay('acquisition-progress_%s' % unique_link, unique_link)
        print("Task started with status ->", result.status)

def get_acquisition_presetup(request, serial_id, unique_link):
    acquisitionObject = Acquisition.objects.get(unique_link=unique_link)

    if ColdForensic().checkSerialID(serial_id) and acquisitionObject:
        return render(request, 'includes/acquisition_setup.html', {})
    else:
        return HttpResponse("Serial ID not found")

def get_acquisition_setup(request, serial_id, unique_link):
    isUniqueCode = Acquisition.objects.filter(unique_link=unique_link).exists()

    if ColdForensic().checkSerialID(serial_id) and isUniqueCode:
        getAcquisitionObject = Acquisition.objects.get(unique_link=unique_link)

        if getAcquisitionObject.status in ["in_progress", "pending", "cancelled", "failed"]:
            if getAcquisitionObject.acquisition_type == "physical":
                return render(request, 'includes/acquisition_progress.html', {'acquisitionObject': getAcquisitionObject})
            if getAcquisitionObject.acquisition_type == "selective_full_file_system":
                return render(request, 'includes/acquisition_progress_spinner.html', {'acquisitionObject': getAcquisitionObject})

    return HttpResponse("Serial ID not found")

def get_acquisition_save_location(request, serial_id, unique_link):
    isUniqueCode = Acquisition.objects.filter(unique_link=unique_link).exists()

    if ColdForensic().checkSerialID(serial_id) and isUniqueCode:
        evidenceList = Evidence.objects.select_related('case').values(
            'evidence_id',
            'evidence_description',
            case_name=F('case__case_name')
        )

        isHashedIP = ColdForensic().is_hashed_ip_or_not(serial_id)
        isWifi = ColdForensic().check_if_hashed_ip(serial_id, ColdForensic().secret_key) if isHashedIP else False
        ipAddress = ColdForensic().decrypt(serial_id, ColdForensic().secret_key).split(':')[0] if isHashedIP else ""
        acquisitionType = Acquisition.objects.get(unique_link=unique_link).acquisition_type

        context ={
            'evidenceList': evidenceList,
            'isWifi': isWifi,
            'ipAddress': ipAddress,
            'acquisitionType': acquisitionType,
        }

        if acquisitionType == "selective_full_file_system":
            return render(request, 'includes/acquisition_save_location_sffs.html', context)

        return render(request, 'includes/acquisition_save_location.html', context)
    else:
        return HttpResponse("Serial ID or Unique not found")

class EvidenceListView(ListView):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    model = Evidence
    fields = '__all__'
    template_name = 'home/evidence.html'
    success_url = reverse_lazy('evidences_home:all')


class EvidenceCreateView(CreateView):

    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    model = Evidence
    template_name = 'home/evidence_create.html'
    fields = ['evidence_description', 'evidence_status', 'evidence_type', 'case',
              'evidence_acquired_by', 'evidence_acquired_date', 'evidence_number']

    def form_invalid(self, form):
        # Log errors
        print(form.errors)
        return super().form_invalid(form)

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        coc_dates = self.request.POST.getlist('coc_date')
        coc_users = self.request.POST.getlist('coc_user')
        coc_actions = self.request.POST.getlist('coc_action')
        coc_details = self.request.POST.getlist('coc_details')

        chain_of_custody_data = []
        for date, user, action, detail in zip(coc_dates, coc_users, coc_actions, coc_details):
            chain_of_custody_data.append({
                'date': date,
                'id': user,
                'user': User.objects.get(id=user).user_name,
                'action': action,
                'detail': detail
            })
        self.object.evidence_chain_of_custody = chain_of_custody_data
        self.object.save()

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['home_case_list'] = Case.objects.all()
        user_list = User.objects.all()
        context['home_user_list'] = json.dumps(list(user_list.values('id', 'user_name')), cls=UUIDEncoder)
        return context

    def get_success_url(self):
        return reverse_lazy('evidences_home')


class EvidenceUpdateView(UpdateView):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    model = Evidence
    template_name = 'home/evidence_update.html'
    form_class = EvidenceUpdateForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_list = User.objects.all()
        context['home_user_list'] = json.dumps(list(user_list.values('id', 'user_name', 'user_email')), cls=UUIDEncoder)

        ChainOfCustodyFormSet = formset_factory(ChainOfCustodyForm, extra=0)

        if self.request.method == 'POST':
            context['chain_of_custody_formset'] = ChainOfCustodyFormSet(self.request.POST)
        else:
            initial_data = self.object.evidence_chain_of_custody
            for data in initial_data:
                data['user'] = data['id']  # Set the initial value for the 'user' field to be the 'id'
            context['chain_of_custody_formset'] = ChainOfCustodyFormSet(initial=initial_data)

        return context

    def get_success_url(self):
        return reverse_lazy('evidences_home')

    def get_object(self, queryset=None):
        evidence_id = self.kwargs['evidence_id']
        return get_object_or_404(Evidence, evidence_id=evidence_id)

    def form_valid(self, form):
        context = self.get_context_data()
        chain_of_custody_formset = context['chain_of_custody_formset']

        if chain_of_custody_formset.is_valid():
            response = super().form_valid(form)

            chain_of_custody_data = []

            for chain_of_custody_form in chain_of_custody_formset:
                if chain_of_custody_form.cleaned_data and not chain_of_custody_form.cleaned_data.get('DELETE'):
                    coc_data = {
                        'date': str(chain_of_custody_form.cleaned_data.get('date')),
                        'id': str(chain_of_custody_form.cleaned_data.get('user').id),
                        'user': chain_of_custody_form.cleaned_data.get('user').user_name,
                        'action': chain_of_custody_form.cleaned_data.get('action'),
                        'detail': chain_of_custody_form.cleaned_data.get('detail')
                    }
                    chain_of_custody_data.append(coc_data)

            self.object.evidence_chain_of_custody = chain_of_custody_data
            self.object.save()

            return response
        else:
            return super().form_invalid(form)


@method_decorator(csrf_exempt, name='dispatch')
class EvidenceDeleteView(View):
    def post(self, request, *args, **kwargs):
        evidence_id = self.kwargs.get('evidence_id')
        evidence = get_object_or_404(Evidence, evidence_id=evidence_id)

        # Perform soft delete
        evidence.is_deleted = True
        evidence.save()

        return JsonResponse({'success': True})

    def get_success_url(self):
        return reverse_lazy('evidences_home')


class Devices(View):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        context = {
            'devList': ColdForensic().get_select_device(),
        }
        html_template = loader.get_template('home/device.html')
        return HttpResponse(html_template.render(context, request))


class DevicesDetail(View):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, dev_id):
        context = {
            'isWiFi': 'true',
            'deviceID': dev_id,
        }

        html_template = loader.get_template('home/device-detail.html')
        return HttpResponse(html_template.render(context, request))


class Analysts(View):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        context = {

        }
        html_template = loader.get_template('home/analyst-report.html')
        return HttpResponse(html_template.render(context, request))


class Profiles(View):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):

        getCaseByUser = Case.objects.filter(case_member=request.user.id).count()
        getEvidenceByUser = Evidence.objects.filter(evidence_acquired_by=request.user.id).count()

        context = {
            'getCaseByUser': getCaseByUser,
            'getEvidenceByUser': getEvidenceByUser,
        }
        html_template = loader.get_template('home/profiles.html')
        return HttpResponse(html_template.render(context, request))


class Acquisitions(View):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, serial_id):

        isDevice = ColdForensic().checkSerialID(serial_id)
        storage = ColdForensic().getStorage(serial_id)
        appList = ColdForensic().getAppList(serial_id)
        isRooted = ColdForensic().isRooted(serial_id)

        if isDevice:
            context = {
                'serial_id': serial_id,
                'storage': storage,
                'appList': appList,
                'isRooted': isRooted,
            }
            html_template = loader.get_template('home/device-acquisition.html')
            return HttpResponse(html_template.render(context, request))
        else:
            return HttpResponse("Device not found")


class AcquisitionSetup(View):

    def get(self, request, serial_id, unique_code):
        isDevice = ColdForensic().checkSerialID(serial_id)
        acquisitionObject = Acquisition.objects.filter(unique_link=unique_code).first()

        if not isDevice or not acquisitionObject:
            return HttpResponse("Device or acquisition process not found")

        isHashedIP = ColdForensic().is_hashed_ip_or_not(serial_id)
        isWifi = ColdForensic().check_if_hashed_ip(serial_id, ColdForensic().secret_key) if isHashedIP else False

        # For FFS method
        if acquisitionObject.acquisition_type == "selective_full_file_system":
            acquisitionHistory = Acquisition.objects.filter(device_id=serial_id, acquisition_type="selective_full_file_system").order_by('-date')
            fileSystemList = ColdForensic().getFullFileSystem(serial_id)

            context = {
                'serial_id': serial_id,
                'file_system_list': fileSystemList,
                'acquisitionHistory': acquisitionHistory,
                'acquisitionProcess': acquisitionObject,
                'isWifi': isWifi
            }

            if isHashedIP:
                context = {
                    'serial_id': serial_id,
                    'acquisitionProcess': acquisitionObject,
                    'file_system_list': fileSystemList,
                    'acquisitionHistory': acquisitionHistory,
                    'isWifi': isWifi,
                    'ipAddress': ColdForensic().decrypt(serial_id, ColdForensic().secret_key).split(':')[0]
                }

            return render(request, 'home/device-acquisition-ffs-setup.html', context)

        # Combine filtering and sorting in one query for clarity and efficiency
        acquisitionList = Acquisition.objects.filter(
            device_id=serial_id,
            acquisition_type='physical'
        ).exclude(status='pending').order_by('-date')

        # Extract and calculate percentages in a more Pythonic way
        percentageList = [
            {
                'percentage': int(100 * (int(data['physical__total_transferred_bytes']) /
                                         (int(data['physical__partition_size']) * 1024)))
            }
            for data in acquisitionList.values('physical__total_transferred_bytes', 'physical__partition_size')
        ]

        acquisitionHistory = zip(acquisitionList, percentageList)

        # Check if the acquisition needs to resume
        if hasattr(acquisitionObject, 'physical') and acquisitionObject.physical.total_transferred_bytes >= 0 and acquisitionObject.status in ["cancelled", "failed", "in_progress"] and acquisitionObject.physical.format_type == "DD":

            # Prepare the context for rendering
            context = {
                'serial_id': serial_id,
                'acquisitionProcess': acquisitionObject,
                'acquisitionHistory': acquisitionHistory,
                'acquisitionPercentage': percentageList,
            }

            if isHashedIP:
                context = {
                    'serial_id': serial_id,
                    'acquisitionProcess': acquisitionObject,
                    'acquisitionHistory': acquisitionHistory,
                    'acquisitionPercentage': percentageList,
                    'isWifi': isWifi,
                    'ipAddress': ColdForensic().decrypt(serial_id, ColdForensic().secret_key).split(':')[0]
                }

            start_acquisition_task(acquisitionObject.unique_link)

            return render(request, 'home/device-acquisition-resume.html', context)

        if acquisitionObject.status in ["completed"]:
            return HttpResponse(f"Task already {acquisitionObject.status}")

        partitionList = ColdForensic().getPartitionList(serial_id)

        largest_partition = None
        if partitionList:
            # `max` will pick the partition with the largest 'blocks'
            largest_partition = max(partitionList, key=lambda p: p["blocks"])

        context = {
            'serial_id': serial_id,
            'partitionList': partitionList,
            'acquisitionProcess': acquisitionObject,
            'acquisitionHistory': acquisitionHistory,
            'isWifi': isWifi,
            'largestPartition': largest_partition,
        }

        if isHashedIP:
            context = {
                'serial_id': serial_id,
                'partitionList': partitionList,
                'acquisitionProcess': acquisitionObject,
                'acquisitionHistory': acquisitionHistory,
                'acquisitionModalHistory': acquisitionList,
                'isWifi': isWifi,
                'ipAddress': ColdForensic().decrypt(serial_id, ColdForensic().secret_key).split(':')[0],
                'largestPartition': largest_partition,
            }

        return render(request, 'home/device-acquisition-physical-setup.html', context)

    def post(self, request, serial_id, unique_code):
        isDevice = ColdForensic().checkSerialID(serial_id)
        acquisitionObject = Acquisition.objects.get(unique_link=unique_code)

        if not isDevice or not acquisitionObject:
            return HttpResponse("Device or acquisition process not found")

        data = {key: value for key, value in request.POST.items() if key != 'csrfmiddlewaretoken'}

        # Check if the device is connected via Wi-Fi or USB
        isHashedIP = ColdForensic().is_hashed_ip_or_not(serial_id)
        isWifi = ColdForensic().check_if_hashed_ip(serial_id, ColdForensic().secret_key) if isHashedIP else False

        connection_type = 'WiFi' if isWifi else 'USB'

        if acquisitionObject.acquisition_type == "physical":
            # Get current time
            current_time = datetime.now().strftime("%Y-%m-%d %Hh%Mm%Ss")

            # Generate a random string for unique identifier
            unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))

            if data['format_type'] == "DD":
                acquisition_file_name = f"{data['partition_id']}_{current_time}_{unique_id}_{connection_type.lower()}.dd"
            elif data['format_type'] == "E01":
                acquisition_file_name = f"{data['partition_id']}_{current_time}_{unique_id}_{connection_type.lower()}"

            # Convert checkbox_value to boolean or integer
            acquisition_is_verify_first = data['checkbox_value'] == 'true'

            # Retrieve the evidence object based on the provided evidence_name
            evidence = Evidence.objects.get(evidence_id=data['evidence_name'])

            # Calculate the acquisition size template (convert partition size to MB)
            acquisition_size_template = round(int(data['partition_size']) / 1000000, 2)

            # Check if a PhysicalAcquisition already exists for this Acquisition
            physical_acquisition, created = PhysicalAcquisition.objects.get_or_create(
                acquisition=acquisitionObject,
                defaults={
                    'partition_id': data['partition_id'],
                    'partition_size': data['partition_size'],
                    'is_verify_first': acquisition_is_verify_first,
                    'acquisition_method': "dd",
                    'format_type': data['format_type'],
                    'source_device': f"/dev/block/{data['partition_id']}",
                }
            )

            # If it already exists, you can update the necessary fields
            if not created:
                physical_acquisition.partition_id = data['partition_id']
                physical_acquisition.partition_size = data['partition_size']
                physical_acquisition.is_verify_first = acquisition_is_verify_first
                physical_acquisition.acquisition_method = "dd"
                physical_acquisition.format_type = data['format_type']
                physical_acquisition.source_device = f"/dev/block/{data['partition_id']}"
                physical_acquisition.save()

            # Check if a custom path is provided
            if not data.get('full_path'):  # Safely handle missing or empty 'full_path'
                # Determine the default Documents directory for the user
                documents_dir = Path.home() / "Documents"

                # Create the CAF directory if it doesn't exist
                caf_dir = documents_dir / "CAF"
                caf_dir.mkdir(parents=True, exist_ok=True)
            else:
                # Use the provided path
                caf_dir = Path(data['full_path'])

            # Handle serial_id and device processing
            device = serial_id
            cold_forensic = ColdForensic()
            if len(serial_id) > 15 and cold_forensic.checkSerialID(serial_id):
                device = cold_forensic.decrypt(serial_id, cold_forensic.secret_key)

            # Get phone type or use default 'unknown'
            phone_type = cold_forensic.decode_bytes_property(
                cold_forensic.getProp(device, 'ro.product.model', 'unknown')
            )

            # Create a unique and structured folder name
            folder_name = f"{phone_type} ({datetime.now().strftime('%Y-%m-%d %Hh%Mm%Ss')})"
            extraction_path = caf_dir / folder_name

            # Attempt to create the folder
            try:
                extraction_path.mkdir(parents=True, exist_ok=True)
                print(f"Folder created at {extraction_path}")
            except OSError as e:
                print(f"Failed to create directory {extraction_path}: {e}")

            acquisitionObject.evidence_id = evidence.evidence_id
            acquisitionObject.connection_type = connection_type
            acquisitionObject.full_path = str(extraction_path)
            acquisitionObject.file_name = acquisition_file_name

            acquisitionObject.client_ip = data.get('client_ip') if data.get('client_ip') != "USB" else ""  # Handle optional fields safely
            acquisitionObject.port = data.get('port') if data.get('port') != "USB" else ""
            acquisitionObject.status = "in_progress"
            acquisitionObject.size = acquisition_size_template

            user = User.objects.get(id=data['examiner'])
            acquisitionObject.examiner = user

            # Save the updated acquisition object
            acquisitionObject.save()

            # Start the task after transaction commits
            transaction.on_commit(lambda: start_acquisition_task(acquisitionObject.unique_link))

            return HttpResponse("Task started..")

        elif acquisitionObject.acquisition_type == "selective_full_file_system":

            # If app_list is missing in data, retrieve it directly from request.body
            if 'app_list' not in data:
                raw_body = request.body.decode('utf-8')  # Decode the raw body to a string
                parsed_body = parse_qs(raw_body)  # Parse the query string to a dictionary
                app_list_str = parsed_body.get('app_list', ['[]'])[
                    0]  # Extract app_list, defaulting to '[]' if not found
            else:
                app_list_str = data.get('app_list', '[]')

            # Convert app_list JSON string to a Python list
            try:
                app_list = json.loads(app_list_str)
            except json.JSONDecodeError:
                app_list = []

            # Retrieve the evidence object based on the provided evidence_name
            evidence = Evidence.objects.get(evidence_id=data['evidence_name'])

            selective_ffs_acquisition, created = SelectiveFullFileSystemAcquisition.objects.get_or_create(
                acquisition=acquisitionObject,
                defaults={
                    'acquisition_tool': 'tar,netcat',
                    'selected_applications': json.loads(data['app_list']),
                    'total_records': len(json.loads(data['app_list'])),
                }
            )

            if not created:
                selective_ffs_acquisition.acquisition_tool = 'tar,netcat'
                selective_ffs_acquisition.selected_applications = json.loads(data['app_list'])
                selective_ffs_acquisition.total_records = len(json.loads(data['app_list']))
                selective_ffs_acquisition.save()

            # Check if a custom path is provided
            if not data.get('full_path'):  # Safely handle missing or empty 'full_path'
                # Determine the default Documents directory for the user
                documents_dir = Path.home() / "Documents"

                # Create the CAF directory if it doesn't exist
                caf_dir = documents_dir / "CAF"
                caf_dir.mkdir(parents=True, exist_ok=True)

            else:
                # Use the provided path
                caf_dir = Path(data['full_path'])

            # Handle serial_id and device processing
            device = serial_id
            cold_forensic = ColdForensic()
            if len(serial_id) > 15 and cold_forensic.checkSerialID(serial_id):
                device = cold_forensic.decrypt(serial_id, cold_forensic.secret_key)

            # Get phone type or use default 'unknown'
            phone_type = cold_forensic.decode_bytes_property(
                cold_forensic.getProp(device, 'ro.product.model', 'unknown')
            )

            # Create a unique and structured folder name
            folder_name = f"{phone_type} ({datetime.now().strftime('%Y-%m-%d %Hh%Mm%Ss')})"
            extraction_path = caf_dir / folder_name

            # Attempt to create the folder
            try:
                extraction_path.mkdir(parents=True, exist_ok=True)
                print(f"Folder created at {extraction_path}")
            except OSError as e:
                print(f"Failed to create directory {extraction_path}: {e}")

            # Update acquisition object
            acquisitionObject.evidence_id = evidence.evidence_id
            acquisitionObject.connection_type = connection_type
            acquisitionObject.full_path = str(extraction_path)
            acquisitionObject.client_ip = data.get('client_ip') if data.get('client_ip') != "USB" else ""  # Handle optional fields safely
            acquisitionObject.port = data.get('port') if data.get('port') != "USB" else ""
            acquisitionObject.status = "in_progress"

            # Save the updated acquisition object
            acquisitionObject.save()

            # Start the task after transaction commits
            transaction.on_commit(lambda: start_acquisition_task(acquisitionObject.unique_link))

            return HttpResponse("Task started..")


class GenerateUniqueCodeView(View):
    def get(self, request, serial_id, acquire_method):
        # Check if the device is valid
        isDevice = ColdForensic().checkSerialID(serial_id)
        if isDevice:

            device = serial_id
            if len(serial_id) > 15 and ColdForensic().checkSerialID(serial_id):
                device = ColdForensic().decrypt(serial_id, ColdForensic().secret_key)

            # Generate and save the new Acquisition process
            unique_code = uuid.uuid4()
            Acquisition.objects.create(
                device_id=serial_id,
                unique_link=unique_code,
                acquisition_type=acquire_method,
                serial_number=ColdForensic().decode_bytes_property(ColdForensic().getProp(device, 'ro.serialno', 'unknown')),
            )
            return JsonResponse({'success': True, 'unique_code': str(unique_code)})
        else:
            return JsonResponse({'success': False}, status=400)