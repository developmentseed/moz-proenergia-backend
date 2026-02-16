from django.core.management.base import BaseCommand
from proenergia.datasets.models import Scenario
from proenergia.datasets.utils import sync_scenario_metrics_with_types


class Command(BaseCommand):
    help = "Sync metrics for scenarios based on DataModel configuration, inferring types for each key"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario-id", type=int, help="Specific scenario ID to sync"
        )

    def handle(self, *args, **options):
        scenario_id = options.get("scenario_id")

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

            # Use utility function that infers types and syncs metrics
            stats = sync_scenario_metrics_with_types(scenario)

            # Display results
            self.stdout.write(f"  Fields synced: {stats['fields_synced']}")
            if stats.get("numeric_fields"):
                self.stdout.write(
                    f'  Numeric fields: {", ".join(stats["numeric_fields"])}'
                )
            if stats.get("string_fields"):
                self.stdout.write(
                    f'  String fields: {", ".join(stats["string_fields"])}'
                )
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ Created {stats['metrics_created']} metrics for scenario {scenario.id}"
                )
            )

        self.stdout.write(self.style.SUCCESS("\n✓ Metrics sync completed"))
