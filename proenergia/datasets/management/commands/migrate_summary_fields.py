from django.core.management.base import BaseCommand
from django.db import transaction
from proenergia.datasets.models import DataModel
import json


class Command(BaseCommand):
    help = "Migrate summary fields to include type property and consolidate from numeric/string fields"

    def handle(self, *args, **options):
        self.stdout.write("Starting migration of summary fields...")

        with transaction.atomic():
            # Process each DataModel
            for model in DataModel.objects.all():
                self.stdout.write(f"\nProcessing model: {model.name}")

                # Get existing fields
                summary_fields = model.summary_fields or []
                numeric_fields = model.summary_numeric_fields or []
                string_fields = model.summary_string_fields or []

                # Create a mapping of column names to field configs
                fields_map = {}

                # First, add type to existing summary_fields
                for field in summary_fields:
                    column = field.get("column")
                    if column:
                        fields_map[column] = field.copy()

                        # Determine type based on the model and column
                        if model.name == "Least Cost Electrification":
                            if column == "Technology2030":
                                fields_map[column]["type"] = "string"
                            elif column in ["Pop2030", "NewHHConnectionsTotal"]:
                                fields_map[column]["type"] = "numeric"

                        elif model.name == "Productive Use of Electricity (PUE)":
                            if column == "PUE_potential":
                                fields_map[column]["type"] = "string"

                        elif model.name == "Mini-grids":
                            if column in ["Technology2030", "Status"]:
                                fields_map[column]["type"] = "string"
                            elif column in [
                                "Pop2030",
                                "NewHHConnectionsTotal",
                                "MGInvestmentCostTotal",
                                "MGInvestmentGenTotal",
                                "MGInvestmentDistTotal",
                                "MGCapacityPV",
                                "MGCapacityDiesel",
                                "MGCapacityBattery",
                                "MGCapacityWind",
                                "MGCapacityHydro",
                                "InstalledCapacity",
                                "ExistingConnections",
                            ]:
                                fields_map[column]["type"] = "numeric"

                        # Default to string if not specified
                        if "type" not in fields_map[column]:
                            fields_map[column]["type"] = "string"

                # Add numeric fields that aren't already in summary_fields
                for column in numeric_fields:
                    if column not in fields_map:
                        field_config = {
                            "column": column,
                            "label": column,  # Use column name as default label
                            "description": "",
                            "type": "numeric",
                        }

                        # Add specific labels for known fields
                        if column == "Pop":
                            field_config["label"] = "Population"
                            field_config["description"] = "Base population"
                        elif column == "GHI":
                            field_config["label"] = "Global Horizontal Irradiance"
                            field_config["description"] = "Solar radiation measure"
                        elif column == "GridCellArea":
                            field_config["label"] = "Grid Cell Area"
                            field_config["description"] = "Area of the grid cell"
                            field_config["unit"] = "km²"

                        fields_map[column] = field_config

                # Add string fields that aren't already in summary_fields
                for column in string_fields:
                    if column not in fields_map:
                        field_config = {
                            "column": column,
                            "label": column,  # Use column name as default label
                            "description": "",
                            "type": "string",
                        }

                        # Add specific labels for known fields
                        if column == "Admin_1":
                            field_config["label"] = "Province"
                            field_config["description"] = "Administrative level 1"
                        elif column == "District":
                            field_config["label"] = "District"
                            field_config["description"] = "Administrative district"
                        elif column == "Posto":
                            field_config["label"] = "Posto"
                            field_config["description"] = "Administrative posto"

                        fields_map[column] = field_config

                # Convert back to list, maintaining order
                new_summary_fields = list(fields_map.values())

                # Update the model
                model.summary_fields = new_summary_fields
                model.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Updated {len(new_summary_fields)} fields for {model.name}"
                    )
                )

                # Show the updates
                for field in new_summary_fields:
                    self.stdout.write(
                        f"    - {field['column']}: {field.get('type', 'unknown')}"
                    )

        self.stdout.write(self.style.SUCCESS("\n✓ Migration completed successfully!"))
