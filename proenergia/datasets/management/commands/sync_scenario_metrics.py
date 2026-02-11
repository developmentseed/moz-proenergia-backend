from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand
from django.db import transaction
from proenergia.datasets.models import Scenario, ScenarioData, ScenarioDataMetrics


class Command(BaseCommand):
    help = "Sync metrics for scenarios based on DataModel configuration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario-id", type=int, help="Specific scenario ID to sync"
        )
        parser.add_argument(
            "--clear", action="store_true", help="Clear existing metrics before syncing"
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Batch size for bulk inserts (default: 5000)",
        )

    def handle(self, *args, **options):
        scenario_id = options.get("scenario_id")
        clear_existing = options.get("clear", False)
        batch_size = options.get("batch_size", 5000)

        if scenario_id:
            scenarios = Scenario.objects.filter(id=scenario_id)
            if not scenarios.exists():
                self.stdout.write(
                    self.style.ERROR(f"Scenario with ID {scenario_id} not found")
                )
                return
        else:
            scenarios = Scenario.objects.all()
            self.stdout.write(
                f"Syncing metrics for all {scenarios.count()} scenarios..."
            )

        for scenario in scenarios:
            self.stdout.write(
                f"\nProcessing scenario {scenario.id} ({scenario.name})..."
            )
            self.sync_scenario_metrics(scenario, clear_existing, batch_size)

        self.stdout.write(self.style.SUCCESS("\n✓ Metrics sync completed"))

    def sync_scenario_metrics(self, scenario, clear_existing=False, batch_size=5000):
        """Extract configured fields to metrics table for a single scenario"""
        model = scenario.model

        # Get configured fields
        numeric_fields = model.summary_numeric_fields or []
        string_fields = model.summary_string_fields or []

        if not numeric_fields and not string_fields:
            self.stdout.write(
                self.style.WARNING(
                    f"  No summary fields configured for model {model.name}"
                )
            )
            return

        self.stdout.write(f'  Numeric fields: {", ".join(numeric_fields)}')
        self.stdout.write(f'  String fields: {", ".join(string_fields)}')

        # Clear existing metrics if requested
        if clear_existing:
            deleted_count = ScenarioDataMetrics.objects.filter(
                scenario=scenario
            ).delete()[0]
            self.stdout.write(f"  Cleared {deleted_count} existing metrics")

        # Count total records to process
        total_records = ScenarioData.objects.filter(scenario=scenario).count()
        self.stdout.write(f"  Processing {total_records} records...")

        # Process in batches
        metrics_to_create = []
        processed = 0
        created = 0

        with transaction.atomic():
            for data in ScenarioData.objects.filter(scenario=scenario).iterator(
                chunk_size=1000
            ):
                # Extract numeric fields
                for field in numeric_fields:
                    if field in data.metadata and data.metadata[field] is not None:
                        try:
                            value = str(data.metadata[field])
                            # Handle scientific notation and convert to Decimal
                            numeric_value = Decimal(value)
                            metrics_to_create.append(
                                ScenarioDataMetrics(
                                    scenario=scenario,
                                    feature_id=data.feature_id,
                                    key=field,
                                    numeric_value=numeric_value,
                                )
                            )
                        except (ValueError, InvalidOperation) as e:
                            # Log the error but continue processing
                            pass

                # Extract string fields
                for field in string_fields:
                    if field in data.metadata and data.metadata[field] is not None:
                        metrics_to_create.append(
                            ScenarioDataMetrics(
                                scenario=scenario,
                                feature_id=data.feature_id,
                                key=field,
                                string_value=str(data.metadata[field]),
                            )
                        )

                processed += 1

                # Bulk insert when batch size is reached
                if len(metrics_to_create) >= batch_size:
                    ScenarioDataMetrics.objects.bulk_create(
                        metrics_to_create, ignore_conflicts=True
                    )
                    created += len(metrics_to_create)
                    metrics_to_create = []

                    # Show progress
                    if processed % 10000 == 0:
                        progress = (processed / total_records) * 100
                        self.stdout.write(
                            f"    {processed}/{total_records} ({progress:.1f}%)"
                        )

            # Insert remaining metrics
            if metrics_to_create:
                ScenarioDataMetrics.objects.bulk_create(
                    metrics_to_create, ignore_conflicts=True
                )
                created += len(metrics_to_create)

        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ Created {created} metrics for scenario {scenario.id}"
            )
        )
