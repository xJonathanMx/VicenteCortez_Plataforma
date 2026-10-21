import io

from django import forms
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from catalogo.models import Servicio
from core.forms import FormEstilo
from core.models import Usuario
from core.permisos import privilegio_requerido

from .generadores import REPORTES


class FiltroReporteForm(FormEstilo):
    desde = forms.DateField(label="Desde", widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(label="Hasta", widget=forms.DateInput(attrs={"type": "date"}))
    peluquero = forms.ModelChoiceField(Usuario.objects.filter(roles__codigo="peluquero").distinct(), required=False,
                                       empty_label="Todos", label="Peluquero")
    servicio = forms.ModelChoiceField(Servicio.objects.select_related("tipo"), required=False, empty_label="Todos",
                                      label="Servicio")


def _filtros(request):
    hoy = timezone.localdate()
    inicial = {"desde": hoy.replace(day=1), "hasta": hoy}
    form = FiltroReporteForm(request.GET or None, initial=inicial)
    if form.is_valid():
        return form, form.cleaned_data
    return FiltroReporteForm(initial=inicial), {**inicial, "peluquero": None, "servicio": None}


@privilegio_requerido("ver_reportes")
def inicio(request):
    return render(request, "reportes/inicio.html", {"reportes": [(k, v[0], v[1]) for k, v in REPORTES.items()]})


@privilegio_requerido("ver_reportes")
def reporte(request, slug):
    if slug not in REPORTES:
        raise Http404
    titulo, descripcion, generar = REPORTES[slug]
    form, f = _filtros(request)
    datos = generar(f)
    formato = request.GET.get("formato")
    subtitulo = f"Del {f['desde']:%d-%m-%Y} al {f['hasta']:%d-%m-%Y}"
    if f.get("peluquero"):
        subtitulo += f", {f['peluquero'].nombre_corto}"
    if f.get("servicio"):
        subtitulo += f", {f['servicio'].nombre}"
    if formato == "xlsx":
        return exportar_excel(slug, titulo, subtitulo, datos)
    if formato == "pdf":
        return exportar_pdf(slug, titulo, subtitulo, datos)
    grafico = None
    if datos.get("grafico") and datos["filas"]:
        ie, iv = datos["grafico"]
        valores = [(r[ie], float(r[iv] or 0)) for r in datos["filas"][:12]]
        maximo = max((v for _, v in valores), default=0) or 1
        grafico = [(e, v, round(v * 100 / maximo)) for e, v in valores]
    return render(request, "reportes/reporte.html", {
        "slug": slug, "titulo": titulo, "descripcion": descripcion, "subtitulo": subtitulo, "form": form,
        "datos": datos, "grafico": grafico})


def _valor(v, i, moneda):
    if i in moneda and isinstance(v, (int, float)):
        return "$" + f"{int(v):,}".replace(",", ".")
    return v


def _resumen(clave, valor):
    """Los totales y montos del resumen se muestran como pesos."""
    es_dinero = isinstance(valor, int) and any(p in clave for p in ("Total", "Monto"))
    return _valor(valor, 0, [0] if es_dinero else [])


def exportar_excel(slug, titulo, subtitulo, datos):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31]
    ws.append([f"Peluquería Vicente Cortez: {titulo}"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([subtitulo])
    ws.append([])
    ws.append(datos["columnas"])
    for c in ws[4]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="000000")
    for fila in datos["filas"]:
        ws.append(fila)
    for i in datos.get("moneda", []):
        for celda in ws.iter_rows(min_row=5, min_col=i + 1, max_col=i + 1):
            celda[0].number_format = '"$"#,##0'
    if datos.get("resumen"):
        ws.append([])
        for k, v in datos["resumen"]:
            ws.append([k, v])
    if datos.get("nota"):
        ws.append([])
        ws.append([datos["nota"]])
    for i, col in enumerate(datos["columnas"], start=1):
        largo = max([len(str(col))] + [len(str(r[i - 1])) for r in datos["filas"]])
        ws.column_dimensions[get_column_letter(i)].width = min(max(12, largo + 2), 50)
    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="reporte-{slug}-{timezone.localdate():%Y%m%d}.xlsx"'
    return resp


def exportar_pdf(slug, titulo, subtitulo, datos):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    ancho = landscape(A4) if len(datos["columnas"]) > 5 else A4
    doc = SimpleDocTemplate(buf, pagesize=ancho, leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm,
                            bottomMargin=1.5 * cm, title=titulo)
    est = getSampleStyleSheet()
    partes = [Paragraph(f"Peluquería Vicente Cortez: {titulo}", est["Title"]), Paragraph(subtitulo, est["Normal"]),
              Spacer(1, 12)]
    moneda = datos.get("moneda", [])
    tabla = [datos["columnas"]] + [[str(_valor(v, i, moneda)) for i, v in enumerate(r)] for r in datos["filas"]]
    if len(tabla) == 1:
        tabla.append(["Sin datos en el período"] + [""] * (len(datos["columnas"]) - 1))
    t = Table(tabla, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#efeff1")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8c8cc")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    partes.append(t)
    if datos.get("resumen"):
        partes.append(Spacer(1, 12))
        for k, v in datos["resumen"]:
            partes.append(Paragraph(f"<b>{k}:</b> {_resumen(k, v)}", est["Normal"]))
    if datos.get("nota"):
        partes.append(Spacer(1, 8))
        partes.append(Paragraph(datos["nota"], est["Italic"]))
    doc.build(partes)
    resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="reporte-{slug}-{timezone.localdate():%Y%m%d}.pdf"'
    return resp
