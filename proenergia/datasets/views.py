from typing import List, Tuple, Union

from django.db.models import Count, Exists, FloatField, Max, Min, OuterRef, QuerySet, Sum
from django.db.models.fields.json import KT
from django.db.models.functions import Cast
from django.db.utils import DataError, InternalError, ProgrammingError
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView, get_object_or_404
from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import ScenarioDataFilter, VectorDatasetFilter
from .models import DataModel, Scenario, ScenarioData, ScenarioDataMetrics, VectorDataset
from .pagination import StandardResultsSetPagination
from .serializers import (
    DataModelSerializer,
    ScenarioDataSerializer,
    VectorDatasetSerializer,
)


class PublicApprovedDataset(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_superuser:
            return True
        elif (
            request.method in SAFE_METHODS
            and request.user.is_authenticated
            and obj.is_approved
        ):
            return True
        else:
            return request.method in SAFE_METHODS and obj.is_public and obj.is_approved


class VectorDatasetListView(ListAPIView):
    """Lists VectorDatasets that are public and approved. For logged-in superadmin users, it returns all datasets."""

    serializer_class = VectorDatasetSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filterset_class = VectorDatasetFilter

    def get_queryset(self):
        queryset = VectorDataset.objects.select_related("created_by", "last_updated_by")
        if self.request.user and self.request.user.is_superuser:
            return queryset
        elif self.request.user.is_authenticated:
            return queryset.filter(is_approved=True)
        else:
            return queryset.filter(is_public=True, is_approved=True)


class VectorDatasetDetailView(RetrieveAPIView):
    """Returns information about a specific VectorDataset."""

    queryset = VectorDataset.objects.all()
    serializer_class = VectorDatasetSerializer
    permission_classes = [PublicApprovedDataset]


class DataModelListView(ListAPIView):
    """Lists all available DataModel entries."""

    queryset = DataModel.objects.prefetch_related("scenarios")
    serializer_class = DataModelSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class DataModelDetailView(RetrieveAPIView):
    """Returns information about a specific DataModel."""

    queryset = DataModel.objects.all()
    serializer_class = DataModelSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class ScenarioDataDetailView(RetrieveAPIView):
    """Returns information about a specific feature of a Scenario's data results."""

    queryset = ScenarioData.objects.all()
    serializer_class = ScenarioDataSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_object(self):
        queryset = self.get_queryset()
        filter = {
            "feature_id": self.kwargs.get("pk"),
            "scenario__id": self.kwargs.get("scenario_id"),
        }
        return get_object_or_404(queryset, **filter)


class SummaryView(APIView):
    """
    High-performance endpoint for computing statistics on scenario metadata fields.
    
    Uses optimized metrics table for sub-second response times on large datasets.
    Only fields configured in DataModel.summary_numeric_fields or summary_string_fields are available.
    
    Returns:
        - Numeric fields: count, min, max, sum
        - String fields: count, value distribution
    
    Supports filtering via ?q= parameter:
        - Numeric: Pop__min=1000, Pop__max=2000  
        - String: Admin_1=Gaza, District__in=Central;Norte
        - Combined: Pop__min=1000,Admin_1=Gaza
    """
    
    # Supported operators for each field type
    NUMERIC_OPERATORS = {'gte', 'lte', 'eq'}
    STRING_OPERATORS = {'eq', 'in'}
    
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get(self, request: Request, pk: int, key: str) -> Response:
        # Verify scenario exists  
        scenario = get_object_or_404(Scenario, id=pk)
        
        # Check if key is available in metrics
        metrics_query = ScenarioDataMetrics.objects.filter(
            scenario=scenario,
            key=key
        )
        
        if not metrics_query.exists():
            # Check if this key is configured for extraction
            model = scenario.model
            configured_keys = (model.summary_numeric_fields or []) + (model.summary_string_fields or [])
            
            if key not in configured_keys:
                return Response(
                    {"error": f"Summary not available for key '{key}'. This field has not been configured for fast summaries."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                return Response(
                    {"error": f"No data found for key '{key}'. The metrics may need to be regenerated."},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Apply filters if provided
        filter_params = request.GET.get('q', '')
        if filter_params:
            try:
                metrics_query = self.apply_metrics_filters(metrics_query, scenario.id, filter_params)
                if isinstance(metrics_query, Response):
                    # Handle validation errors returned by filter method
                    return metrics_query
            except ValueError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Check if numeric or string field
        sample = metrics_query.first()
        if sample and sample.numeric_value is not None:
            # Numeric aggregation
            aggregates = metrics_query.aggregate(
                max_val=Max('numeric_value'),
                min_val=Min('numeric_value'), 
                sum_val=Sum('numeric_value'),
                count=Count('numeric_value')
            )
            summary = {
                "key": key,
                "type": "numeric",
                "count": aggregates['count'] or 0,
                "min": float(aggregates['min_val']) if aggregates['min_val'] is not None else None,
                "max": float(aggregates['max_val']) if aggregates['max_val'] is not None else None,
                "sum": float(aggregates['sum_val']) if aggregates['sum_val'] is not None else None
            }
        else:
            # String aggregation
            values = metrics_query.values('string_value').annotate(
                count=Count('id')
            ).order_by('string_value')
            
            summary = {
                "key": key,
                "type": "string",
                "count": sum(v['count'] for v in values),
                "values": {v['string_value']: v['count'] for v in values if v['string_value'] is not None}
            }
        
        return Response(summary)
    
    def apply_metrics_filters(
        self, 
        queryset: QuerySet, 
        scenario_id: int, 
        filter_string: str
    ) -> QuerySet:
        """Apply filters to metrics queryset using SQL EXISTS subqueries for efficiency."""
        if not queryset.exists():
            return queryset
            
        # Get field type information from DataModel
        scenario = queryset.first().scenario
        model = scenario.model
        numeric_fields = set(model.summary_numeric_fields or [])
        string_fields = set(model.summary_string_fields or [])
        
        # Parse and validate filters
        filters = self.parse_filter_string(filter_string)
        
        # Apply each filter as an EXISTS subquery
        for field_name, operator, value in filters:
            # Validate field is configured
            if field_name not in numeric_fields and field_name not in string_fields:
                raise ValueError(f"Field '{field_name}' is not configured for summaries.")
            
            # Validate operator is appropriate for field type
            self._validate_field_operator(field_name, operator, numeric_fields, string_fields)
            
            # Create and apply EXISTS subquery filter
            exists_subquery = self._build_exists_subquery(
                scenario_id, field_name, operator, value, numeric_fields
            )
            queryset = queryset.filter(Exists(exists_subquery))
        
        return queryset
    
    def parse_filter_string(self, filter_string: str) -> List[Tuple[str, str, Union[str, List[str]]]]:
        """Parse filter string into (field_name, operator, value) tuples."""
        filters = []
        for part in filter_string.split(','):
            if '=' in part:
                key_op, value = part.split('=', 1)
                key_op = key_op.strip()
                value = value.strip()
                
                # Parse operator
                if '__min' in key_op:
                    filters.append((key_op.replace('__min', ''), 'gte', value))
                elif '__max' in key_op:
                    filters.append((key_op.replace('__max', ''), 'lte', value))
                elif '__in' in key_op:
                    filters.append((key_op.replace('__in', ''), 'in', value.split(';')))
                else:
                    filters.append((key_op, 'eq', value))
        return filters
    
    def _validate_field_operator(
        self, 
        field_name: str, 
        operator: str, 
        numeric_fields: set, 
        string_fields: set
    ) -> None:
        """Validate that the operator is appropriate for the field type."""
        if field_name in numeric_fields and operator not in self.NUMERIC_OPERATORS:
            raise ValueError(f"Operator '{operator}' is not supported for numeric field '{field_name}'.")
        
        if field_name in string_fields and operator not in self.STRING_OPERATORS:
            raise ValueError(f"Operator '{operator}' is not supported for string field '{field_name}'.")
        
        # Specific validation for string fields with numeric operators
        if field_name in string_fields and operator in {'gte', 'lte'}:
            raise ValueError(f"Min/max operations are not supported for string field '{field_name}'.")
    
    def _build_exists_subquery(
        self, 
        scenario_id: int, 
        field_name: str, 
        operator: str, 
        value: Union[str, List[str]], 
        numeric_fields: set
    ) -> QuerySet:
        """Build EXISTS subquery for the given filter condition."""
        exists_subquery = ScenarioDataMetrics.objects.filter(
            scenario_id=scenario_id,
            feature_id=OuterRef('feature_id'),
            key=field_name
        )
        
        if field_name in numeric_fields:
            # Handle numeric field operations
            try:
                numeric_val = float(value)
                if operator == 'gte':
                    exists_subquery = exists_subquery.filter(numeric_value__gte=numeric_val)
                elif operator == 'lte':
                    exists_subquery = exists_subquery.filter(numeric_value__lte=numeric_val)
                elif operator == 'eq':
                    exists_subquery = exists_subquery.filter(numeric_value=numeric_val)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid numeric value '{value}' for field '{field_name}'.")
        else:
            # Handle string field operations
            if operator == 'eq':
                exists_subquery = exists_subquery.filter(string_value=value)
            elif operator == 'in':
                # Ensure value is a list for 'in' operations
                value_list = value if isinstance(value, list) else [value]
                exists_subquery = exists_subquery.filter(string_value__in=value_list)
        
        return exists_subquery
