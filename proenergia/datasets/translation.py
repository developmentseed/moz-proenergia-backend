from modeltranslation.translator import TranslationOptions, translator

from .models import DataModel, Scenario, VectorDataset


class NameTranslationOptions(TranslationOptions):
    fields = ["name"]


class NameDescriptionTranslationOptions(TranslationOptions):
    fields = ("name", "description")


translator.register(DataModel, NameDescriptionTranslationOptions)
translator.register(VectorDataset, NameDescriptionTranslationOptions)
translator.register(Scenario, NameTranslationOptions)
