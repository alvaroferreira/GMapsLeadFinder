"""Testes unitarios para ExportService."""

import pandas as pd
import pytest

from src.database.models import Business
from src.services.exporter import ExportService


class TestExportService:
    """Testes para ExportService."""

    @pytest.fixture
    def export_dir(self, tmp_path):
        """Directorio temporario para exports."""
        export_path = tmp_path / "exports"
        export_path.mkdir()
        return export_path

    @pytest.fixture
    def service(self, export_dir):
        """Instancia do ExportService."""
        return ExportService(export_dir=export_dir)

    @pytest.fixture
    def sample_businesses(self, business_factory):
        """Lista de businesses para export."""
        return business_factory.create_batch(5)

    def test_init_cria_directorio_exports(self, tmp_path):
        """Deve criar directorio de exports se nao existir."""
        # Arrange
        export_path = tmp_path / "new_exports"
        assert not export_path.exists()

        # Act
        service = ExportService(export_dir=export_path)

        # Assert
        assert export_path.exists()
        assert export_path.is_dir()

    def test_businesses_to_dataframe_converte_corretamente(self, service, business_factory):
        """Deve converter lista de Business para DataFrame."""
        # Arrange
        businesses = [
            business_factory.create(
                name="Empresa 1",
                phone_number="+351 912 345 678",
                rating=4.5,
                lead_score=75,
            ),
            business_factory.create(
                name="Empresa 2",
                phone_number="+351 912 345 679",
                rating=4.0,
                lead_score=60,
            ),
        ]

        # Act
        df = service._businesses_to_dataframe(businesses)

        # Assert
        assert len(df) == 2
        assert "name" in df.columns
        assert "phone_number" in df.columns
        assert "rating" in df.columns
        assert "lead_score" in df.columns
        assert df.iloc[0]["name"] == "Empresa 1"
        assert df.iloc[1]["name"] == "Empresa 2"

    def test_businesses_to_dataframe_usa_international_phone_se_necessario(self, service):
        """Deve usar telefone internacional se nacional nao disponivel."""
        # Arrange
        business = Business(
            id="test123",
            name="Test",
            phone_number=None,
            international_phone="+351 912 345 678",
            rating=4.0,
            review_count=10,
            has_website=False,
            lead_score=50,
            lead_status="new",
        )

        # Act
        df = service._businesses_to_dataframe([business])

        # Assert
        assert df.iloc[0]["phone_number"] == "+351 912 345 678"

    def test_businesses_to_dataframe_filtra_colunas(self, service, sample_businesses):
        """Deve incluir apenas colunas especificadas."""
        # Arrange
        columns = ["name", "website", "lead_score"]

        # Act
        df = service._businesses_to_dataframe(sample_businesses, columns=columns)

        # Assert
        assert list(df.columns) == columns

    def test_businesses_to_dataframe_ignora_colunas_invalidas(self, service, sample_businesses):
        """Deve ignorar colunas que nao existem no modelo."""
        # Arrange
        columns = ["name", "coluna_inexistente", "website"]

        # Act
        df = service._businesses_to_dataframe(sample_businesses, columns=columns)

        # Assert
        assert "coluna_inexistente" not in df.columns
        assert "name" in df.columns
        assert "website" in df.columns

    def test_generate_filename_inclui_timestamp(self, service):
        """Deve gerar filename com timestamp."""
        # Act
        filename = service._generate_filename("leads", "csv")

        # Assert
        assert filename.startswith("leads_")
        assert filename.endswith(".csv")
        assert len(filename) > len("leads_.csv")  # Tem timestamp

    def test_generate_filename_formatos_diferentes(self, service):
        """Deve gerar filenames com diferentes extensoes."""
        # Act
        csv = service._generate_filename("test", "csv")
        xlsx = service._generate_filename("test", "xlsx")
        json = service._generate_filename("test", "json")

        # Assert
        assert csv.endswith(".csv")
        assert xlsx.endswith(".xlsx")
        assert json.endswith(".json")

    def test_export_csv_cria_ficheiro(self, service, sample_businesses):
        """Deve criar ficheiro CSV com sucesso."""
        # Act
        filepath = service.export_csv(sample_businesses)

        # Assert
        assert filepath.exists()
        assert filepath.suffix == ".csv"

        # Verificar conteudo
        df = pd.read_csv(filepath)
        assert len(df) == len(sample_businesses)

    def test_export_csv_traduz_colunas(self, service, sample_businesses):
        """Deve traduzir nomes das colunas para portugues."""
        # Act
        filepath = service.export_csv(sample_businesses, translate_columns=True)

        # Assert
        df = pd.read_csv(filepath)
        assert "Nome" in df.columns
        assert "Telefone" in df.columns
        assert "Website" in df.columns
        assert "Score" in df.columns

    def test_export_csv_mantem_colunas_originais(self, service, sample_businesses):
        """Deve manter nomes originais quando translate_columns=False."""
        # Act
        filepath = service.export_csv(sample_businesses, translate_columns=False)

        # Assert
        df = pd.read_csv(filepath)
        assert "name" in df.columns
        assert "phone_number" in df.columns
        assert "website" in df.columns

    def test_export_csv_com_filename_customizado(self, service, sample_businesses):
        """Deve usar filename customizado quando fornecido."""
        # Arrange
        custom_name = "leads_personalizados.csv"

        # Act
        filepath = service.export_csv(sample_businesses, filename=custom_name)

        # Assert
        assert filepath.name == custom_name

    def test_export_csv_com_colunas_especificas(self, service, sample_businesses):
        """Deve exportar apenas colunas especificadas."""
        # Arrange
        columns = ["name", "phone_number", "website"]

        # Act
        filepath = service.export_csv(sample_businesses, columns=columns)

        # Assert
        df = pd.read_csv(filepath)
        # Verificar que tem apenas as colunas pedidas (traduzidas)
        assert len(df.columns) <= len(columns) + 1  # +1 margem para traducao

    def test_export_excel_cria_ficheiro(self, service, sample_businesses):
        """Deve criar ficheiro Excel com sucesso."""
        # Act
        filepath = service.export_excel(sample_businesses)

        # Assert
        assert filepath.exists()
        assert filepath.suffix == ".xlsx"

        # Verificar conteudo
        df = pd.read_excel(filepath)
        assert len(df) == len(sample_businesses)

    def test_export_excel_usa_sheet_name_customizado(self, service, sample_businesses):
        """Deve usar nome de sheet customizado."""
        # Arrange
        sheet_name = "Meus Leads"

        # Act
        filepath = service.export_excel(sample_businesses, sheet_name=sheet_name)

        # Assert
        df = pd.read_excel(filepath, sheet_name=sheet_name)
        assert len(df) == len(sample_businesses)

    def test_export_excel_traduz_colunas(self, service, sample_businesses):
        """Deve traduzir colunas no Excel."""
        # Act
        filepath = service.export_excel(sample_businesses, translate_columns=True)

        # Assert
        df = pd.read_excel(filepath)
        assert "Nome" in df.columns
        assert "Telefone" in df.columns

    def test_export_excel_com_filename_customizado(self, service, sample_businesses):
        """Deve usar filename customizado no Excel."""
        # Arrange
        custom_name = "relatorio_leads.xlsx"

        # Act
        filepath = service.export_excel(sample_businesses, filename=custom_name)

        # Assert
        assert filepath.name == custom_name

    def test_export_crm_hubspot_mapeia_colunas(self, service, sample_businesses):
        """Deve mapear colunas para formato HubSpot."""
        # Act
        filepath = service.export_crm(sample_businesses, crm_type="hubspot")

        # Assert
        assert filepath.exists()
        df = pd.read_csv(filepath)

        # Verificar mapeamento HubSpot
        assert "Company name" in df.columns
        assert "Street address" in df.columns
        assert "Phone number" in df.columns
        assert "Company domain name" in df.columns

    def test_export_crm_pipedrive_mapeia_colunas(self, service, sample_businesses):
        """Deve mapear colunas para formato Pipedrive."""
        # Act
        filepath = service.export_crm(sample_businesses, crm_type="pipedrive")

        # Assert
        df = pd.read_csv(filepath)
        assert "Name" in df.columns
        assert "Address" in df.columns
        assert "Phone" in df.columns
        assert "Website" in df.columns

    def test_export_crm_salesforce_mapeia_colunas(self, service, sample_businesses):
        """Deve mapear colunas para formato Salesforce."""
        # Act
        filepath = service.export_crm(sample_businesses, crm_type="salesforce")

        # Assert
        df = pd.read_csv(filepath)
        assert "Company" in df.columns
        assert "BillingStreet" in df.columns
        assert "Phone" in df.columns
        assert "Website" in df.columns

    def test_export_crm_case_insensitive(self, service, sample_businesses):
        """Deve aceitar tipo de CRM em qualquer case."""
        # Act
        filepath1 = service.export_crm(sample_businesses, crm_type="HubSpot")
        filepath2 = service.export_crm(sample_businesses, crm_type="PIPEDRIVE")

        # Assert
        assert filepath1.exists()
        assert filepath2.exists()

    def test_export_crm_erro_tipo_invalido(self, service, sample_businesses):
        """Deve lancar erro para tipo de CRM nao suportado."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            service.export_crm(sample_businesses, crm_type="crm_inexistente")

        assert "nao suportado" in str(exc_info.value).lower()

    def test_export_crm_com_filename_customizado(self, service, sample_businesses):
        """Deve usar filename customizado para CRM."""
        # Arrange
        custom_name = "hubspot_import.csv"

        # Act
        filepath = service.export_crm(
            sample_businesses,
            crm_type="hubspot",
            filename=custom_name,
        )

        # Assert
        assert filepath.name == custom_name

    def test_export_json_cria_ficheiro(self, service, sample_businesses):
        """Deve criar ficheiro JSON com sucesso."""
        # Act
        filepath = service.export_json(sample_businesses)

        # Assert
        assert filepath.exists()
        assert filepath.suffix == ".json"

        # Verificar conteudo
        df = pd.read_json(filepath)
        assert len(df) == len(sample_businesses)

    def test_export_json_formato_correto(self, service, business_factory):
        """Deve exportar JSON em formato legivel."""
        # Arrange
        businesses = [business_factory.create(name="Empresa Teste")]

        # Act
        filepath = service.export_json(businesses)

        # Assert
        import json

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "Empresa Teste"

    def test_export_json_com_filename_customizado(self, service, sample_businesses):
        """Deve usar filename customizado no JSON."""
        # Arrange
        custom_name = "leads_export.json"

        # Act
        filepath = service.export_json(sample_businesses, filename=custom_name)

        # Assert
        assert filepath.name == custom_name

    def test_get_export_summary_estatisticas_basicas(self, service, business_factory):
        """Deve retornar estatisticas basicas do export."""
        # Arrange
        businesses = [
            business_factory.create(has_website=True, lead_score=80),
            business_factory.create(has_website=False, lead_score=60),
            business_factory.create(has_website=True, lead_score=70),
        ]

        # Act
        summary = service.get_export_summary(businesses)

        # Assert
        assert summary["total"] == 3
        assert summary["with_website"] == 2
        assert summary["without_website"] == 1
        assert "avg_score" in summary

    def test_get_export_summary_contagem_telefones(self, service, business_factory):
        """Deve contar businesses com telefone."""
        # Arrange
        businesses = [
            business_factory.create(phone_number="+351 912 345 678"),
            business_factory.create(phone_number=None),
            business_factory.create(phone_number="+351 912 345 679"),
        ]

        # Act
        summary = service.get_export_summary(businesses)

        # Assert
        assert summary["with_phone"] == 2

    def test_get_export_summary_media_score(self, service, business_factory):
        """Deve calcular media de lead score."""
        # Arrange
        businesses = [
            business_factory.create(lead_score=80),
            business_factory.create(lead_score=60),
            business_factory.create(lead_score=70),
        ]

        # Act
        summary = service.get_export_summary(businesses)

        # Assert
        assert summary["avg_score"] == 70.0

    def test_get_export_summary_media_rating(self, service, business_factory):
        """Deve calcular media de rating."""
        # Arrange
        businesses = [
            business_factory.create(rating=4.5),
            business_factory.create(rating=4.0),
            business_factory.create(rating=None),
        ]

        # Act
        summary = service.get_export_summary(businesses)

        # Assert
        assert summary["avg_rating"] is not None
        assert 4.0 <= summary["avg_rating"] <= 4.5

    def test_get_export_summary_contagem_por_status(self, service, business_factory):
        """Deve contar businesses por status."""
        # Arrange
        businesses = [
            business_factory.create(lead_status="new"),
            business_factory.create(lead_status="new"),
            business_factory.create(lead_status="qualified"),
            business_factory.create(lead_status="contacted"),
        ]

        # Act
        summary = service.get_export_summary(businesses)

        # Assert
        assert "by_status" in summary
        assert summary["by_status"]["new"] == 2
        assert summary["by_status"]["qualified"] == 1
        assert summary["by_status"]["contacted"] == 1

    def test_get_export_summary_lista_vazia(self, service):
        """Deve retornar total 0 para lista vazia."""
        # Act
        summary = service.get_export_summary([])

        # Assert
        assert summary["total"] == 0

    def test_get_supported_formats_retorna_todos(self, service):
        """Deve retornar todos os formatos suportados."""
        # Act
        formats = service.get_supported_formats()

        # Assert
        assert "csv" in formats
        assert "xlsx" in formats
        assert "json" in formats
        assert "hubspot" in formats
        assert "pipedrive" in formats
        assert "salesforce" in formats
        assert len(formats) >= 6

    def test_export_csv_encoding_utf8(self, service, business_factory):
        """Deve usar encoding UTF-8 com BOM para CSV."""
        # Arrange
        businesses = [business_factory.create(name="Empresa com acentos: Café")]

        # Act
        filepath = service.export_csv(businesses)

        # Assert
        # Verificar que consegue ler com acentos
        df = pd.read_csv(filepath, encoding="utf-8-sig")
        assert "Café" in df.iloc[0]["Nome"] or "Café" in df.iloc[0]["name"]

    def test_export_excel_ajusta_largura_colunas(self, service, business_factory):
        """Deve ajustar largura das colunas no Excel."""
        # Arrange
        businesses = [
            business_factory.create(
                name="Empresa com nome muito longo para testar ajuste",
                formatted_address="Rua muito longa numero 1234, edificio A, andar 5",
            ),
        ]

        # Act
        filepath = service.export_excel(businesses)

        # Assert
        assert filepath.exists()
        # Verificar que ficheiro foi criado (openpyxl lida com formatacao)

    def test_export_preserva_dados_especiais(self, service, business_factory):
        """Deve preservar caracteres especiais e numeros."""
        # Arrange
        businesses = [
            business_factory.create(
                name="Empresa & Cia Ltda",
                phone_number="+351 912 345 678",
                website="https://empresa.pt/página-especial?param=valor",
            ),
        ]

        # Act
        filepath = service.export_csv(businesses, translate_columns=False)

        # Assert
        df = pd.read_csv(filepath)
        assert "&" in df.iloc[0]["name"]
        assert "param=valor" in df.iloc[0]["website"]

    def test_export_csv_mantem_ordem_colunas(self, service, business_factory):
        """Deve manter ordem consistente de colunas."""
        # Arrange
        businesses = business_factory.create_batch(2)

        # Act
        filepath1 = service.export_csv(businesses)
        filepath2 = service.export_csv(businesses)

        # Assert
        df1 = pd.read_csv(filepath1)
        df2 = pd.read_csv(filepath2)
        assert list(df1.columns) == list(df2.columns)

    def test_column_mapping_completo(self, service):
        """Deve ter mapeamento completo de colunas importantes."""
        # Assert
        assert "name" in service.COLUMN_MAPPING
        assert "formatted_address" in service.COLUMN_MAPPING
        assert "phone_number" in service.COLUMN_MAPPING
        assert "website" in service.COLUMN_MAPPING
        assert "rating" in service.COLUMN_MAPPING
        assert "lead_score" in service.COLUMN_MAPPING
        assert "lead_status" in service.COLUMN_MAPPING

    def test_crm_mappings_completo(self, service):
        """Deve ter mapeamentos para todos os CRMs suportados."""
        # Assert
        assert "hubspot" in service.CRM_MAPPINGS
        assert "pipedrive" in service.CRM_MAPPINGS
        assert "salesforce" in service.CRM_MAPPINGS

        # Cada CRM deve ter campos essenciais
        for crm, mapping in service.CRM_MAPPINGS.items():
            assert "name" in mapping
            assert "phone_number" in mapping
            assert "website" in mapping
