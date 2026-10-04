from src.schema import FINANCIALS, MARKET, OPERATING, Campo


def test_los_esquemas_declaran_trazabilidad():
    """Todo esquema debe exigir fuente y fecha de obtencion en cada fila."""
    for esquema in (FINANCIALS, OPERATING, MARKET):
        nombres = {c.nombre for c in esquema.campos}
        assert "source" in nombres
        assert "retrieved_at" in nombres


def test_financials_incluye_los_dos_segmentos_reportables():
    """Tesla declara dos segmentos bajo ASC 280, no tres."""
    nombres = {c.nombre for c in FINANCIALS.campos}
    for esperado in (
        "revenue_auto_segment", "cogs_auto_segment", "gross_profit_auto_segment",
        "revenue_energy_segment", "cogs_energy_segment", "gross_profit_energy_segment",
    ):
        assert esperado in nombres


def test_financials_incluye_las_lineas_de_producto_de_automocion():
    """Las cuatro lineas que Tesla publica DENTRO del segmento de automocion."""
    nombres = {c.nombre for c in FINANCIALS.campos}
    for esperado in (
        "revenue_total", "revenue_auto_sales", "revenue_auto_leasing",
        "revenue_reg_credits", "revenue_services",
    ):
        assert esperado in nombres


def test_operating_guarda_el_literal_y_las_series_homogeneas():
    """La nomenclatura de Tesla cambio en 2020: hay que guardar ambas cosas."""
    nombres = {c.nombre for c in OPERATING.campos}
    for esperado in (
        "deliveries_volumen", "deliveries_nicho",
        "production_volumen", "production_nicho",
        "etiqueta_volumen", "etiqueta_nicho",
    ):
        assert esperado in nombres


def test_operating_no_incluye_los_mw_solares():
    """KPI excluido: no consta con cifra en el Update Letter."""
    assert "solar_deployed_mw" not in {c.nombre for c in OPERATING.campos}


def test_cada_campo_declara_tipo_y_unidad():
    for esquema in (FINANCIALS, OPERATING, MARKET):
        for campo in esquema.campos:
            assert isinstance(campo, Campo)
            assert campo.tipo in ("str", "float", "int")
            assert campo.unidad is not None


def test_la_clave_de_financials_es_el_periodo():
    assert FINANCIALS.clave == ["period"]


def test_financials_incluye_lo_que_necesita_la_valoracion():
    nombres = {c.nombre for c in FINANCIALS.campos}
    for esperado in (
        "short_term_investments", "total_debt", "da", "income_tax",
        "pretax_income", "filing_date",
    ):
        assert esperado in nombres


def test_bpa_y_acciones_diluidas_son_opcionales():
    """Su Q4 no se puede reconstruir: el hueco es intencionado."""
    opcionales = {c.nombre for c in FINANCIALS.campos if not c.obligatorio}
    assert {"eps_diluted_gaap", "shares_diluted"} <= opcionales


def test_la_fecha_de_publicacion_es_obligatoria():
    """Sin ella los multiplos mirarian al futuro."""
    fecha = next(c for c in FINANCIALS.campos if c.nombre == "filing_date")
    assert fecha.obligatorio


def test_mercado_incluye_lo_que_necesita_el_capm():
    nombres = {c.nombre for c in MARKET.campos}
    assert {"spy_close", "rf_10y"} <= nombres
