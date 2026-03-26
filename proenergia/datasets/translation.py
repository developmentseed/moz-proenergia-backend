from modeltranslation.translator import TranslationOptions, translator

from .models import DataModel, RasterDataset, Scenario, VectorDataset


class NameTranslationOptions(TranslationOptions):
    fields = ["name"]
    required_languages = ["en"]


class NameDescriptionTranslationOptions(TranslationOptions):
    fields = ["name", "description"]
    required_languages = ["en"]


translator.register(DataModel, NameDescriptionTranslationOptions)
translator.register(VectorDataset, NameDescriptionTranslationOptions)
translator.register(RasterDataset, NameDescriptionTranslationOptions)
translator.register(Scenario, NameTranslationOptions)
