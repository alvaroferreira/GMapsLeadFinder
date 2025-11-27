"""Servico de exportacao de leads."""

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import settings
from src.database.models import Business


class ExportService:
    """Servico para exportar leads em varios formatos."""

    # Mapeamento de colunas para portugues
    COLUMN_MAPPING = {
        "name": "Nome",
        "formatted_address": "Endereco",
        "phone_number": "Telefone",
        "website": "Website",
        "rating": "Rating",
        "review_count": "Reviews",
        "lead_score": "Score",
        "lead_status": "Status",
        "first_seen_at": "Descoberto Em",
        "google_maps_url": "Google Maps",
        "notes": "Notas",
        "place_id": "Place ID",
    }

    # Mapeamentos para CRMs
    CRM_MAPPINGS = {
        "hubspot": {
            "name": "Company name",
            "formatted_address": "Street address",
            "phone_number": "Phone number",
            "website": "Company domain name",
            "notes": "Description",
            "google_maps_url": "Google Maps URL",
        },
        "pipedrive": {
            "name": "Name",
            "formatted_address": "Address",
            "phone_number": "Phone",
            "website": "Website",
            "notes": "Notes",
        },
        "salesforce": {
            "name": "Company",
            "formatted_address": "BillingStreet",
            "phone_number": "Phone",
            "website": "Website",
            "rating": "Rating",
            "notes": "Description",
        },
    }

    def __init__(self, export_dir: Path | None = None):
        """
        Inicializa o servico.

        Args:
            export_dir: Directorio para exports (opcional)
        """
        self.export_dir = export_dir or settings.export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def _businesses_to_dataframe(
        self,
        businesses: list[Business],
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Converte lista de Business para DataFrame.

        Args:
            businesses: Lista de negocios
            columns: Colunas a incluir (opcional)

        Returns:
            DataFrame pandas
        """
        data = []
        for b in businesses:
            row = {
                "name": b.name,
                "formatted_address": b.formatted_address,
                "phone_number": b.phone_number or b.international_phone,
                "website": b.website,
                "rating": b.rating,
                "review_count": b.review_count,
                "lead_score": b.lead_score,
                "lead_status": b.lead_status,
                "first_seen_at": b.first_seen_at,
                "google_maps_url": b.google_maps_url,
                "notes": b.notes,
                "place_id": b.id,
                "latitude": b.latitude,
                "longitude": b.longitude,
                "has_website": b.has_website,
                "photo_count": b.photo_count,
            }
            data.append(row)

        df = pd.DataFrame(data)

        if columns:
            available = [c for c in columns if c in df.columns]
            df = df[available]

        return df

    def _generate_filename(self, prefix: str, extension: str) -> str:
        """Gera nome de ficheiro com timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}.{extension}"

    def export_csv(
        self,
        businesses: list[Business],
        filename: str | None = None,
        translate_columns: bool = True,
        columns: list[str] | None = None,
    ) -> Path:
        """
        Exporta para CSV.

        Args:
            businesses: Lista de negocios
            filename: Nome do ficheiro (opcional)
            translate_columns: Traduzir nomes das colunas
            columns: Colunas a incluir

        Returns:
            Path do ficheiro criado
        """
        df = self._businesses_to_dataframe(businesses, columns)

        if translate_columns:
            df = df.rename(columns=self.COLUMN_MAPPING)

        if not filename:
            filename = self._generate_filename("leads", "csv")

        filepath = self.export_dir / filename
        df.to_csv(filepath, index=False, encoding="utf-8-sig")

        return filepath

    def export_excel(
        self,
        businesses: list[Business],
        filename: str | None = None,
        sheet_name: str = "Leads",
        translate_columns: bool = True,
    ) -> Path:
        """
        Exporta para Excel com formatacao.

        Args:
            businesses: Lista de negocios
            filename: Nome do ficheiro
            sheet_name: Nome da sheet
            translate_columns: Traduzir colunas

        Returns:
            Path do ficheiro criado
        """
        df = self._businesses_to_dataframe(businesses)

        if translate_columns:
            df = df.rename(columns=self.COLUMN_MAPPING)

        if not filename:
            filename = self._generate_filename("leads", "xlsx")

        filepath = self.export_dir / filename

        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            # Formatacao
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]

            # Auto-ajustar largura das colunas
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).map(len).max() if len(df) > 0 else 0,
                    len(str(col)),
                ) + 2
                # Converter indice para letra de coluna
                col_letter = chr(65 + idx) if idx < 26 else chr(64 + idx // 26) + chr(65 + idx % 26)
                worksheet.column_dimensions[col_letter].width = min(max_length, 50)

            # Estilo do header
            from openpyxl.styles import Font, PatternFill

            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(
                start_color="4472C4",
                end_color="4472C4",
                fill_type="solid",
            )

            for cell in worksheet[1]:
                cell.font = header_font
                cell.fill = header_fill

        return filepath

    def export_crm(
        self,
        businesses: list[Business],
        crm_type: str,
        filename: str | None = None,
    ) -> Path:
        """
        Exporta em formato compativel com CRM.

        Args:
            businesses: Lista de negocios
            crm_type: Tipo de CRM (hubspot, pipedrive, salesforce)
            filename: Nome do ficheiro

        Returns:
            Path do ficheiro criado

        Raises:
            ValueError: Se CRM nao suportado
        """
        crm_type = crm_type.lower()

        if crm_type not in self.CRM_MAPPINGS:
            supported = ", ".join(self.CRM_MAPPINGS.keys())
            raise ValueError(f"CRM '{crm_type}' nao suportado. Suportados: {supported}")

        df = self._businesses_to_dataframe(businesses)
        mapping = self.CRM_MAPPINGS[crm_type]

        # Selecionar e renomear colunas
        available_cols = [c for c in mapping.keys() if c in df.columns]
        df = df[available_cols]
        df = df.rename(columns=mapping)

        if not filename:
            filename = self._generate_filename(f"leads_{crm_type}", "csv")

        filepath = self.export_dir / filename
        df.to_csv(filepath, index=False, encoding="utf-8-sig")

        return filepath

    def export_json(
        self,
        businesses: list[Business],
        filename: str | None = None,
    ) -> Path:
        """
        Exporta para JSON.

        Args:
            businesses: Lista de negocios
            filename: Nome do ficheiro

        Returns:
            Path do ficheiro criado
        """
        df = self._businesses_to_dataframe(businesses)

        if not filename:
            filename = self._generate_filename("leads", "json")

        filepath = self.export_dir / filename
        df.to_json(filepath, orient="records", indent=2, force_ascii=False)

        return filepath

    def get_export_summary(self, businesses: list[Business]) -> dict[str, Any]:
        """
        Retorna resumo dos dados a exportar.

        Args:
            businesses: Lista de negocios

        Returns:
            Dict com estatisticas
        """
        if not businesses:
            return {"total": 0}

        df = self._businesses_to_dataframe(businesses)

        return {
            "total": len(businesses),
            "with_website": int(df["has_website"].sum()),
            "without_website": int((~df["has_website"]).sum()),
            "with_phone": int(df["phone_number"].notna().sum()),
            "avg_score": round(df["lead_score"].mean(), 1),
            "avg_rating": round(df["rating"].mean(), 2) if df["rating"].notna().any() else None,
            "by_status": df["lead_status"].value_counts().to_dict(),
        }

    @staticmethod
    def get_supported_formats() -> list[str]:
        """Retorna formatos de exportacao suportados."""
        return ["csv", "xlsx", "json", "hubspot", "pipedrive", "salesforce"]
