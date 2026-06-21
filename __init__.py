"""ComfyUI-Ideogram-Palette-and-Prompt-Tools node registration."""

from .nodes.palette_extractor import IdeogramPaletteExtractor
from .nodes.palette_to_json import IdeogramPaletteToGlobalJSON
from .nodes.palette_override import IdeogramPaletteOverride
from .nodes.element_palette import IdeogramElementPalette
from .nodes.metadata_embedder import IdeogramMetadataEmbedder
from .nodes.palette_blend import IdeogramPaletteBlend
from .nodes.metadata_reader import IdeogramMetadataReader
from .nodes.json_validator import IdeogramJSONValidator
from .nodes.prompt_assembler import IdeogramPromptAssembler
from .nodes.metadata_file_reader import IdeogramLoadImageWithPrompt
from .nodes.masked_palette_extractor import IdeogramMaskedPaletteExtractor
from .nodes.vibrant_palette_extractor import IdeogramVibrantPaletteExtractor
from .nodes.element_builder import IdeogramElementBuilder, IdeogramElementCollector

NODE_CLASS_MAPPINGS = {
    "IdeogramPaletteExtractor": IdeogramPaletteExtractor,
    "IdeogramPaletteToGlobalJSON": IdeogramPaletteToGlobalJSON,
    "IdeogramPaletteOverride": IdeogramPaletteOverride,
    "IdeogramElementPalette": IdeogramElementPalette,
    "IdeogramMetadataEmbedder": IdeogramMetadataEmbedder,
    "IdeogramPaletteBlend": IdeogramPaletteBlend,
    "IdeogramMetadataReader": IdeogramMetadataReader,
    "IdeogramJSONValidator": IdeogramJSONValidator,
    "IdeogramPromptAssembler": IdeogramPromptAssembler,
    "IdeogramLoadImageWithPrompt": IdeogramLoadImageWithPrompt,
    "IdeogramMaskedPaletteExtractor": IdeogramMaskedPaletteExtractor,
    "IdeogramVibrantPaletteExtractor": IdeogramVibrantPaletteExtractor,
    "IdeogramElementBuilder": IdeogramElementBuilder,
    "IdeogramElementCollector": IdeogramElementCollector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "IdeogramPaletteExtractor": "Ideogram Palette Extractor",
    "IdeogramPaletteToGlobalJSON": "Ideogram Palette -> Global JSON",
    "IdeogramPaletteOverride": "Ideogram Palette Override",
    "IdeogramElementPalette": "Ideogram Element Palette",
    "IdeogramMetadataEmbedder": "Ideogram Metadata Embedder",
    "IdeogramPaletteBlend": "Ideogram Palette Blend",
    "IdeogramMetadataReader": "Ideogram Metadata Reader",
    "IdeogramJSONValidator": "Ideogram JSON Validator",
    "IdeogramPromptAssembler": "Ideogram Prompt Assembler",
    "IdeogramLoadImageWithPrompt": "Ideogram Load Image With Prompt",
    "IdeogramMaskedPaletteExtractor": "Ideogram Masked Palette Extractor",
    "IdeogramVibrantPaletteExtractor": "Ideogram Vibrant Palette Extractor",
    "IdeogramElementBuilder": "Ideogram Element Builder",
    "IdeogramElementCollector": "Ideogram Element Collector",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
