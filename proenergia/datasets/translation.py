from modeltranslation.translator import TranslationOptions, translator

from .models import DataModel, RasterDataset, ReferenceDataset, Scenario, VectorDataset


class NameTranslationOptions(TranslationOptions):
    fields = ["name"]
    required_languages = ["en"]


class NameDescriptionTranslationOptions(TranslationOptions):
    fields = ["name", "description"]
    required_languages = ["en"]


class DataModelTranslationOptions(TranslationOptions):
    fields = ["name", "description", "visualization_column_description"]
    required_languages = ["en"]


translator.register(DataModel, DataModelTranslationOptions)
translator.register(VectorDataset, NameDescriptionTranslationOptions)
translator.register(RasterDataset, NameDescriptionTranslationOptions)
translator.register(ReferenceDataset, NameDescriptionTranslationOptions)
translator.register(Scenario, NameTranslationOptions)
