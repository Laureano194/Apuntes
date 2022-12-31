import json
from datetime import datetime

from django.db import transaction
from django.db.models.fields import BooleanField, DateField
from django.core.exceptions import ValidationError
from django.http.response import JsonResponse
from django.db.models import Q, F, Count, OuterRef, Subquery, CharField, Value, BooleanField, Case, When
from django.db.models.functions import Concat

from rest_framework.authentication import TokenAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, authentication_classes, permission_classes, parser_classes

from p_03_Presupuesto.models import Presupuesto
from Imputaciones.SeparacionImputaciones import CreateUnicaSeparacion
from users.Permisos_Check import TienePermiso

from utilities import list_utils, list_reports

from Imputaciones.models import Imputaciones, Porcentajes, SeparacionImputaciones, MontoADistribuirSeparaciones, DetalleSeparaciones, MontoADistribuirSeparaciones, Solicitudes

from misc.Configuraciones import EnviarMailSeparacionImputacion


@api_view(['GET'])
@authentication_classes((TokenAuthentication, BasicAuthentication))
@permission_classes((IsAuthenticated, ))
def List(request):
    nro_subquery = Presupuesto.objects.values('plan__solicitud__id').filter(plan__solicitud__id=OuterRef('solicitud__id')).order_by('-pk')
    obj_data = json.loads(request.GET.get('data'))

    if request.user.is_superuser:
        distribuir = True
    else:
        distribuir = 'imputaciones_imputaciones_distribuir' in request.user.perfil.GetPermisos()

    db_query= Imputaciones.objects.annotate(
        cod=Subquery(nro_subquery.values('nro')[:1], CharField()),
        codigo=F('solicitud__codigo'),
        titulo=F('solicitud__nombre'),
        empr_org=F('empresa__nombre'),
    ).annotate(
        distribuir=Value(distribuir, output_field=BooleanField()),
        imputar=Case(
            When(personalDistribucion__perfil__user__id=request.user.id, then=Value(True)),
            default=Value(request.user.is_superuser, output_field=BooleanField()),
            output_field=BooleanField(),
        ),
        fechaEstado=Case(
            When(estado='E-LTP', then=F('fechaELTP')),
            When(estado='E-OTT', then=F('fechaEOTT')),
            default=Value(None, output_field=DateField()),
            output_field=DateField(),
        )
    )
    user = request.user
    if not TienePermiso(user, "administrador") and not TienePermiso(user, "soberana"):
        userId = user.perfil.persona_id
        db_query = db_query.filter(personalDistribucion__id=userId)

    return list_utils.obj_tables_default(db_query, obj_data)


@api_view(['POST'])
@authentication_classes((TokenAuthentication, BasicAuthentication))
@permission_classes((IsAuthenticated, ))
def Create(request):
    obj_data = json.loads(request.body)

    porcentajes = obj_data.pop('porcentajes')

    dict_errors = dict()
    try:
        with transaction.atomic():
            new_obj = Imputaciones(**obj_data)

            new_obj.monto = round(new_obj.monto, 2)
            new_obj.porcentajeUVT = round(new_obj.porcentajeUVT, 2)
            new_obj.insumosDirectos = round(new_obj.insumosDirectos, 2)
            new_obj.porcentajeFPLQ = round(new_obj.porcentajeFPLQ, 2)
            new_obj.porcentajeEjecutores = round(new_obj.porcentajeEjecutores, 2)

            new_obj.full_clean()
            new_obj.save()

            for p in porcentajes:
                porc = Porcentajes()
                porc.label = p['label']
                porc.porcentaje = round(p['porcentaje'], 2)
                porc.imputacion = new_obj
                if porc.porcentaje > 0: porc.save()

            nro_subquery = Presupuesto.objects.values('plan__solicitud__id').filter(plan__solicitud__id=OuterRef('solicitud__id')).order_by('-pk')
            new_obj = Imputaciones.objects.annotate(
                cod=Subquery(nro_subquery.values('nro')[:1], CharField()),
                codigo=F('solicitud__codigo'),
            ).get(pk=new_obj.pk)

            CreateUnicaSeparacion(new_obj)

        return JsonResponse({"success": True, "pk": new_obj.pk})
    except ValidationError as e:
        Imputaciones.objects.filter(pk=new_obj.pk).delete()
        for v in e:
            dict_errors[v[0]] = v[1][0]
        return JsonResponse({"success": False, "errors": dict_errors})


@api_view(['GET'])
@authentication_classes((TokenAuthentication, BasicAuthentication))
@permission_classes((IsAuthenticated, ))
def Detail(request, id):
    db_subquery = Presupuesto.objects.values('plan__solicitud__id').filter(plan__solicitud__id=OuterRef('solicitud__id')).order_by('-pk')
    obj = Imputaciones.objects.filter(id=id).annotate(
        cod=Subquery(db_subquery.values('nro')[:1], CharField()),
    ).first()
    return JsonResponse(obj.json(), safe=False)


def cerrar_is_valid(id):
    imputacion = Imputaciones.objects.get(pk=id)
    is_valid = True
    for separacion in imputacion.separacionimputaciones_set.all():
        is_valid = is_valid and separacion.montoadistribuirseparaciones_set.count() > 0
    return is_valid

@api_view(['GET', 'POST'])
@authentication_classes((TokenAuthentication, BasicAuthentication))
@permission_classes((IsAuthenticated, ))
def Edit(request, id):
    obj = Imputaciones.objects.get(pk=id)
    if request.method == "POST":

        obj_data = json.loads(request.body)

        porcentajes = obj_data.pop('porcentajes')

        if "cerrada" in obj_data and obj_data['cerrada'] and not cerrar_is_valid(id):
             return JsonResponse({
                "success": False,
                "errors": {"cerrada": "No es posible cerrar, asigne monto a distribuir"}
             })

        dict_errors = dict()

        try:
            with transaction.atomic():
                for attr, value in obj_data.items():
                    setattr(obj, attr, value)

                obj.monto = round(obj.monto, 2)
                obj.porcentajeUVT = round(obj.porcentajeUVT, 2)
                obj.insumosDirectos = round(obj.insumosDirectos, 2)
                obj.porcentajeFPLQ = round(obj.porcentajeFPLQ, 2)
                obj.porcentajeEjecutores = round(obj.porcentajeEjecutores, 2)

                obj.full_clean()
                obj.save()

                obj.porcentajes.all().delete()

                for p in porcentajes:
                    porc = Porcentajes()
                    porc.label = p['label']
                    porc.porcentaje = round(p['porcentaje'], 2)
                    porc.imputacion = obj
                    if porc.porcentaje > 0: porc.save()

                # nro_subquery = Presupuesto.objects.values('plan__solicitud__id').filter(plan__solicitud__id=OuterRef('solicitud__id')).order_by('-pk')
                # obj = Imputaciones.objects.annotate(
                #     cod=Subquery(nro_subquery.values('nro')[:1], CharField()),
                #     codigo=F('solicitud__codigo'),
                # ).get(pk=obj.pk)

                # CreateUnicaSeparacion(obj) --> Este método crea una separacion nueva idéntica a la existente cuando se guarda una edición. Puede ser resultado de un
                # copy-paste, o bien es necesario crear una nueva eliminando la anterior.

            return JsonResponse({"success": True})
        except ValidationError as e:
            for v in e:
                dict_errors[v[0]] = v[1][0]
            return JsonResponse({"success": False, "errors": dict_errors})
    else:
        obj = Imputaciones.objects.get(pk=id)
        return JsonResponse(obj.json(), safe=False)


@api_view(['GET', 'POST'])
@authentication_classes((TokenAuthentication, BasicAuthentication))
@permission_classes((IsAuthenticated, ))
def Delete(request, id):
    obj = Imputaciones.objects.get(pk=id)
    if request.method == "POST":
        try:
            obj.delete()
            return JsonResponse({"success": True})
        except:
            return JsonResponse({"success": False})
    else:
        return JsonResponse(obj.json(), safe=False)


def Export(request):
    obj_data = json.loads(request.GET.get('data'))
    db_query = Imputaciones.objects.filter(debaja=False).annotate(Count('empresas'))
    return list_reports.file_default_export(db_query, 'Imputaciones', obj_data)


def checkIsLider(user_id, id_imputacion):
    try:
        imputacion = Imputaciones.objects.get(id=id_imputacion)
        return imputacion.personalDistribucion.perfil.user.id == user_id
    except Imputaciones.DoesNotExist:
        return JsonResponse(
            {
                "success": False,
                "error": {"Imputacion": "No Existe"}
            }
        )


@api_view(['POST'])
@authentication_classes((TokenAuthentication, BasicAuthentication))
@permission_classes((IsAuthenticated, ))
def Distribuir(request, id):

    if checkIsLider(request.user.id, id):
        return JsonResponse({
            "success": False,
            "error": {"Lider": "Funcion Deshabilitada: Lider Técnico, no puede distribuir"}
        })

    if request.method == "POST":
        obj_data = json.loads(request.body)

        sendMail = obj_data.get('sendMail', False)

        # Capturo los id que no se deben eliminar
        idDelete = [s['id'] for s in obj_data['separaciones'] if ('id' in s) and (s['id']!=None)]
        # Elimino las separaciones
        SeparacionImputaciones.objects.filter(Q(imputacion_id = id) & ~Q(id__in=idDelete)).delete()

        ar_emails = []

        for d in obj_data['separaciones']:
            # Si se edita una capturo la misma
            if(('id' in d) and (d['id']!=None)):
                new_separacion = SeparacionImputaciones.objects.get(id=d['id'])
            else:
                # Sino creo una nueva
                new_separacion = SeparacionImputaciones(pk=None)
            new_separacion.personal_id = d['personal_id']
            new_separacion.monto = round(d['monto'], 2)
            new_separacion.nombre = d['nombre']
            new_separacion.imputacion_id = d['imputacion_id']
            new_separacion.save()

            if(new_separacion.personal.email!=None):
                ar_emails.append(new_separacion.personal.email)

        obj = Imputaciones.objects.get(pk=id)

        if(sendMail==True and len(ar_emails)>0):
            EnviarMailSeparacionImputacion(obj.json(), ar_emails)

            obj.estado = 'E-LTP'
            obj.fechaELTP = datetime.now()
            obj.save()


        return JsonResponse({"success": True, "imputacion": obj.json()})


@api_view(['GET'])
@authentication_classes((TokenAuthentication, BasicAuthentication))
@permission_classes((IsAuthenticated, ))
def Participaciones(request):
    if request.method == "GET":
        obj_data = json.loads(request.GET.get('data'))

        iduser = None
        for f in obj_data['table']['filtered']:
            if(f['id']=='user_id'):
                iduser = f['value']

        db_subquery = Presupuesto.objects.values('plan__solicitud__id').filter(plan__solicitud__id=OuterRef('separacion__imputacion__solicitud__id')).order_by('-pk')

        db_query = MontoADistribuirSeparaciones.objects.filter(personal_id__isnull=False).annotate(user_id=F('personal__perfil__user_id'))
        if(iduser!=None):
            db_query = db_query.filter(user_id=iduser)

        db_query = db_query.annotate(
            fechaDeFacturacion = F('separacion__imputacion__fechaDeFacturacion'),
            fechaDeCobro = F('separacion__imputacion__fechaDeCobro'),
            empresa_nombre = F('separacion__imputacion__empresa__razonSocial'),
            nroProyecto=Subquery(db_subquery.values('nro')[:1], CharField()),
            personal_nombre = Concat('personal__apellido', Value(', '), 'personal__nombre'),
            imputacion_id = F('separacion__imputacion_id'),
        )

        return list_utils.obj_tables_default(db_query, obj_data)


@api_view(['GET', 'POST'])
@authentication_classes((TokenAuthentication, BasicAuthentication))
@permission_classes((IsAuthenticated, ))
def FinalizarImputacion(request, id):
    if not (checkIsLider(request.user.id, id) or request.user.is_superuser):
        return JsonResponse({
            "success": False,
            "error": {"Lider": "Funcion Deshabilitada: No posee los permisos necesarios."}
        })
    db_subquery = Presupuesto.objects.values('plan__solicitud__id').filter(plan__solicitud__id=OuterRef('solicitud__id')).order_by('-pk')

    obj = Imputaciones.objects.filter(id=id).annotate(
        cod=Subquery(db_subquery.values('nro')[:1], CharField()),
    ).first()

    presupuesto = Presupuesto.objects.annotate(
        solicitud_id=F('plan__solicitud__id'),
    ).filter(solicitud_id=obj.solicitud_id).order_by('pk').last()

    if request.method == 'POST':
        ar_emails = [presupuesto.ott.email]

        dict_data = {
            'nroPresupuesto': obj.cod,
            'nroFactura': obj.nroFactura,
        }

        # EnviarMailImputacionOTT(dict_data, ar_emails)

        obj.estado = 'E-OTT'
        obj.fechaEOTT = datetime.now()
        obj.save()

        return JsonResponse({"success": True, "imputacion": obj.json()})
    else:
        return JsonResponse({"success": True, "imputacion": obj.json(), "ott_nombre": presupuesto.ott.nombre, "ott_email":presupuesto.ott.email})


@api_view(['GET', 'POST'])
@authentication_classes((TokenAuthentication, BasicAuthentication))
@permission_classes((IsAuthenticated, ))
def MailLiderTecnico(request, id):
    db_subquery = Presupuesto.objects.values('plan__solicitud__id').filter(plan__solicitud__id=OuterRef('solicitud__id')).order_by('-pk')

    obj = Imputaciones.objects.filter(id=id).annotate(
        cod=Subquery(db_subquery.values('nro')[:1], CharField()),
    ).first()

    presupuesto = Presupuesto.objects.annotate(
        solicitud_id=F('plan__solicitud__id'),
    ).filter(solicitud_id=obj.solicitud_id).order_by('pk').last()

    if request.method == 'POST':
        if(obj.personalDistribucion.email != None):
            EnviarMailSeparacionImputacion(obj.json(), [obj.personalDistribucion.email])
        obj.estado = 'E-LTP'
        obj.fechaELTP = datetime.now()
        obj.save()

        return JsonResponse({"success": True, "imputacion": obj.json()})
    else:
        return JsonResponse({"success": True, "imputacion": obj.json(), "ott_nombre": presupuesto.ott.nombre, "ott_email":presupuesto.ott.email})


def formatCurrency(val):
    val = "{:,.2f}".format(round(val, 2))
    val = val.replace(".", "..").replace(",",",,")
    val = val.replace("..", ",").replace(",,",".")
    return val
def formatPercent(val):
    val = "{:,.2f}".format(round(val, 6))
    val = val.replace(".", "..").replace(",",",,")
    val = val.replace("..", ",").replace(",,",".")
    return val

def GenerarReporteDict(separacion_id=0, imputacion_id=0):
    data = {}
    if separacion_id != None and int(separacion_id) > 0:
        obj = SeparacionImputaciones.objects.get(pk=separacion_id)
        obj_imputacion = Imputaciones.objects.get(pk=obj.imputacion_id)
    elif imputacion_id != None and int(imputacion_id) > 0:
        obj_imputacion = Imputaciones.objects.get(pk=imputacion_id)
        obj = SeparacionImputaciones.objects.filter(imputacion_id = imputacion_id).order_by('id').last()

    presupuesto = Presupuesto.objects.filter(plan__solicitud=obj_imputacion.solicitud).order_by('pk').last()

    data.update({
        'proyecto': obj_imputacion.solicitud.nombre,
        'presupuesto': obj_imputacion.solicitud.GetCode(),
        'uvt': presupuesto.uvt.nombre,
        'empresa': obj_imputacion.empresa.razonSocial,
        'nroFactura': obj_imputacion.nroFactura,
        'fechaFacturacion': obj_imputacion.fechaDeFacturacion.strftime("%d/%m/%Y"),
        'fechaCobro': obj_imputacion.fechaDeCobro.strftime("%d/%m/%Y"),
        'monto': formatCurrency(obj_imputacion.monto),

        '_monto': round(obj_imputacion.monto, 4)
    })

    data.update({
        'porcUVT': formatPercent(obj_imputacion.porcentajeUVT),
        'montoUVT': formatCurrency(obj_imputacion.monto * obj_imputacion.porcentajeUVT / 100),
        'insumosDirectos': formatCurrency(obj_imputacion.insumosDirectos),

        '_porcUVT': round(obj_imputacion.porcentajeUVT, 6),
        '_insumosDirectos': round(obj_imputacion.insumosDirectos, 2),
    })

    sutotalDistribuir = obj_imputacion.monto-((obj_imputacion.porcentajeUVT*obj_imputacion.monto)/100)-obj_imputacion.insumosDirectos
    data.update({
        'sutotalParaDistribuir': formatCurrency(sutotalDistribuir),
    })

    costos = 0
    for ds in DetalleSeparaciones.objects.filter(Q(separacion_id = obj.id)).all(): costos += ds.monto
    subtotal = obj.monto - costos
    data.update({
        'montoSeparacion': formatCurrency(obj.monto),
        'costos': formatCurrency(costos),
        'sutotal': formatCurrency(obj.monto - costos),
        'porcFuncionamientoPLQ': formatPercent(obj.funcionamientoPLQ),
        'montoFuncionamientoPLQ': formatCurrency(subtotal * obj.funcionamientoPLQ / 100),
        'porcEjecutores': formatPercent(obj.ejecutores),
        'montoEjecutores': formatCurrency(subtotal * obj.ejecutores / 100),
        'porcentajesRestantes': [
            (p.label, formatPercent(p.porcentaje), formatCurrency(subtotal * p.porcentaje / 100)) for p in obj.porcentajes.all()
        ],

        '_porcEjecutores': round(obj.ejecutores, 6),
        '_porcFuncionamientoPLQ': round(obj.funcionamientoPLQ, 6),
        '_porcentajesRestantes': [
            (p.label, round(p.porcentaje, 6)) for p in obj.porcentajes.all() # (subtotal * p.porcentaje / 100)
        ],
    })

    data.update({
        'tituloSeparaciones': [
            (ds.tituloSeparaciones.nombre, ds.grupo.nombre, formatCurrency(ds.monto)) for ds in DetalleSeparaciones.objects.filter(Q(separacion_id = obj.id)).all()
        ],
        'montoSeparacionesGruposYEjecutores': [(
                ("Grupo - " + mds.grupo.nombre) if mds.grupo_id is not None else ("Ejecutor - " + mds.personal.apellido + " " +mds.personal.nombre),
                formatPercent(mds.porcentaje),
                formatCurrency(mds.monto)
            ) for mds in MontoADistribuirSeparaciones.objects.filter(Q(separacion_id = obj.id) & (Q(personal_id__isnull=False) | Q(grupo_id__isnull=False))).order_by('grupo')
        ],

        '_tituloSeparaciones': [
            (ds.tituloSeparaciones.nombre, ds.grupo.nombre, round(ds.monto, 6)) for ds in DetalleSeparaciones.objects.filter(Q(separacion_id = obj.id)).all()
        ],
        '_montoSeparacionesGruposYEjecutores': [(
                ("Grupo - " + mds.grupo.nombre) if mds.grupo_id is not None else ("Ejecutor - " + mds.personal.apellido + " " +mds.personal.nombre),
                round(mds.porcentaje, 6),
                'g' if mds.grupo_id is not None else 'e'
            ) for mds in MontoADistribuirSeparaciones.objects.filter(Q(separacion_id = obj.id) & (Q(personal_id__isnull=False) | Q(grupo_id__isnull=False))).order_by('grupo')
        ]
    })

    montoADistribuirSeparaciones = MontoADistribuirSeparaciones.objects.filter(Q(separacion_id = obj.id)).order_by('grupo')
    subtotalGrupos = 0
    subtotalEjecutores = 0
    for mds in montoADistribuirSeparaciones:
        if mds.grupo is not None:
            subtotalGrupos += mds.monto
        else:
            subtotalEjecutores += mds.monto

    data.update({
        'subtotalGrupos':formatCurrency(subtotalGrupos),
        'subtotalEjecutores':formatCurrency(subtotalEjecutores),
    })

    return data