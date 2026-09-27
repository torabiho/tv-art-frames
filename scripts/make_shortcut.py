"""Build an unsigned 'Wall Art.shortcut' (binary plist). Sign on macOS with:
   shortcuts sign -m anyone -i "Wall Art.unsigned.shortcut" -o "Wall Art.shortcut"
"""
import plistlib, uuid

import os
BASE_URL = os.environ.get("FRAMES_URL", "https://raw.githubusercontent.com/USER/tv-art-frames/main")
CANVAS_W, CANVAS_H = 2048, 1152
OBJ = "￼"


def var(name):
    return {"Value": {"Type": "Variable", "VariableName": name},
            "WFSerializationType": "WFTextTokenAttachment"}


def text(*parts):
    """parts: str or ('var', name). Returns a WFTextTokenString."""
    s, att = "", {}
    for p in parts:
        if isinstance(p, tuple):
            att[f"{{{len(s)}, 1}}"] = {"Type": "Variable", "VariableName": p[1]}
            s += OBJ
        else:
            s += p
    if not att:
        return s
    return {"Value": {"string": s, "attachmentsByRange": att},
            "WFSerializationType": "WFTextTokenString"}


def act(ident, **params):
    return {"WFWorkflowActionIdentifier": ident, "WFWorkflowActionParameters": params}


def setvar(name, inp=None):
    p = {"WFVariableName": name}
    if inp is not None:
        p["WFInput"] = inp
    return act("is.workflow.actions.setvariable", **p)


def getkey(dict_var, key, out):
    return [act("is.workflow.actions.getvalueforkey", WFInput=var(dict_var),
                WFDictionaryKey=key, WFGetDictionaryValueType="Value"),
            setvar(out)]


def geturl(url_text, out):
    return [act("is.workflow.actions.downloadurl", WFURL=url_text, WFHTTPMethod="GET"),
            setvar(out)]


def getfile(path_text, out):
    return [act("is.workflow.actions.documentpicker.open", WFGetFilePath=path_text,
                WFShowFilePicker=False, WFFileErrorIfNotFound=True),
            setvar(out)]


actions = []
actions += [act("is.workflow.actions.comment",
                WFCommentActionText="Wall Art: pick a frame and photos, get framed 2048x1152 JPEGs to add to the TV Art shared album. Frames are downloaded from the TV Art Frames GitHub repo.")]
# 1. frames.json -> dictionary
actions += geturl(f"{BASE_URL}/frames.json", "ManifestFile")
actions += [act("is.workflow.actions.detect.dictionary", WFInput=var("ManifestFile")), setvar("Manifest")]
actions += getkey("Manifest", "catalog", "Frames")
# 2. choose frame
actions += [act("is.workflow.actions.getvalueforkey", WFInput=var("Frames"),
                WFGetDictionaryValueType="All Keys"), setvar("FrameNames")]
actions += [act("is.workflow.actions.choosefromlist", WFInput=var("FrameNames"),
                WFChooseFromListActionPrompt="Choose a frame"), setvar("FrameName")]
actions += [act("is.workflow.actions.getvalueforkey", WFInput=var("Frames"),
                WFDictionaryKey=text(("var", "FrameName")), WFGetDictionaryValueType="Value"),
            setvar("Variants")]
# 2b. mat choice; a frame with a single variant is picked automatically, no question shown
actions += [act("is.workflow.actions.getvalueforkey", WFInput=var("Variants"),
                WFGetDictionaryValueType="All Keys"), setvar("VariantNames")]
# only ask when the frame really has a choice; a one-item list is still shown by iOS
MAT = str(uuid.uuid4()).upper()
actions += [act("is.workflow.actions.count", WFCountType="Items", Input=var("VariantNames"), WFInput=var("VariantNames")),
            setvar("VariantCount"),
            act("is.workflow.actions.conditional", WFInput={"Type": "Variable", "Variable": var("VariantCount")},
                WFCondition=2, WFNumberValue=1, GroupingIdentifier=MAT, WFControlFlowMode=0),
            act("is.workflow.actions.choosefromlist", WFInput=var("VariantNames"),
                WFChooseFromListActionPrompt="With or without mat?"), setvar("VariantName"),
            act("is.workflow.actions.conditional", GroupingIdentifier=MAT, WFControlFlowMode=1),
            act("is.workflow.actions.getitemfromlist", WFInput=var("VariantNames"), WFItemSpecifier="First Item"),
            setvar("VariantName"),
            act("is.workflow.actions.conditional", GroupingIdentifier=MAT, WFControlFlowMode=2)]
actions += [act("is.workflow.actions.getvalueforkey", WFInput=var("Variants"),
                WFDictionaryKey=text(("var", "VariantName")), WFGetDictionaryValueType="Value"),
            setvar("Frame")]
for k, out in [("file", "FileName"), ("x", "X"), ("y", "Y"), ("w", "W"), ("h", "H"), ("id", "FrameId")]:
    actions += getkey("Frame", k, out)
# 3. load frame images
actions += geturl(text(f"{BASE_URL}/frames/", ("var", "FileName")), "FrameImage")
actions += geturl(f"{BASE_URL}/ui/dim.png", "DimImage")
# 4. pick photos
actions += [act("is.workflow.actions.selectphoto", WFSelectMultiplePhotos=True), setvar("Photos")]
# 5. loop
grp = str(uuid.uuid4()).upper()
ORIENT = str(uuid.uuid4()).upper()
actions += [act("is.workflow.actions.repeat.each", WFInput=var("Photos"),
                GroupingIdentifier=grp, WFControlFlowMode=0)]
actions += [
    # every frame window is wider than 16:9, so fit-to-width then centre-crop fills it
    # HDR photos (10-bit HLG / Display P3) wash out when composited; flatten to an SDR JPEG first
    act("is.workflow.actions.image.convert", WFInput=var("Repeat Item"), WFImageFormat="JPEG",
        WFImageCompressionQuality=1.0, WFImagePreserveMetadata=False),
    setvar("Sdr"),
    # --- vertical or horizontal? ---
    act("is.workflow.actions.properties.images", WFInput=var("Sdr"), WFContentItemPropertyName="Width"),
    setvar("PhotoW"),
    act("is.workflow.actions.properties.images", WFInput=var("Sdr"), WFContentItemPropertyName="Height"),
    setvar("PhotoH"),
    act("is.workflow.actions.math", WFInput=var("PhotoH"), WFMathOperation="-", WFMathOperand=text(("var", "PhotoW"))),
    setvar("Diff"),
    act("is.workflow.actions.conditional", WFInput={"Type": "Variable", "Variable": var("Diff")},
        WFCondition=2, WFNumberValue=0, GroupingIdentifier=ORIENT, WFControlFlowMode=0),
    # VERTICAL: whole photo, centred, over a blurred and darkened zoomed-in copy of itself.
    # The background is built 112 px larger than the window, blurred, then centre-cropped,
    # so the unblended edges left by the shifted copies fall outside the frame.
    act("is.workflow.actions.math", WFInput=var("W"), WFMathOperation="+", WFMathOperand=112),
    setvar("BgW"),
    act("is.workflow.actions.math", WFInput=var("H"), WFMathOperation="+", WFMathOperand=112),
    setvar("BgH"),
    act("is.workflow.actions.image.resize", WFImage=var("Sdr"), WFInput=var("Sdr"),
        WFImageResizeWidth=text(("var", "BgW")), WFImageResizeHeight="Auto"),
    setvar("BgWide"),
    act("is.workflow.actions.image.crop", WFInput=var("BgWide"), WFImageCropPosition="Center",
        WFImageCropWidth=text(("var", "BgW")), WFImageCropHeight=text(("var", "BgH"))),
    setvar("BgCrop"),
    # Shortcuts has no blur: shrink to 30 px wide, scale back up (blocky),
    # then average shifted copies of itself to smooth the blocks out.
    act("is.workflow.actions.image.resize", WFImage=var("BgCrop"), WFInput=var("BgCrop"),
        WFImageResizeWidth="30", WFImageResizeHeight="Auto"),
    setvar("BgTiny"),
    act("is.workflow.actions.image.resize", WFImage=var("BgTiny"), WFInput=var("BgTiny"),
        WFImageResizeWidth=text(("var", "BgW")), WFImageResizeHeight=text(("var", "BgH"))),
    setvar("Soft"),
    act("is.workflow.actions.overlayimageonimage", WFInput=var("Soft"), WFImage=var("Soft"),
        WFShouldShowImageEditor=False, WFImagePosition="Custom",
        WFImageX="8", WFImageY="0", WFImageWidth=text(("var", "BgW")), WFImageHeight=text(("var", "BgH")),
        WFRotation="0", WFOverlayImageOpacity="50"),
    setvar("Soft"),
    act("is.workflow.actions.overlayimageonimage", WFInput=var("Soft"), WFImage=var("Soft"),
        WFShouldShowImageEditor=False, WFImagePosition="Custom",
        WFImageX="16", WFImageY="0", WFImageWidth=text(("var", "BgW")), WFImageHeight=text(("var", "BgH")),
        WFRotation="0", WFOverlayImageOpacity="50"),
    setvar("Soft"),
    act("is.workflow.actions.overlayimageonimage", WFInput=var("Soft"), WFImage=var("Soft"),
        WFShouldShowImageEditor=False, WFImagePosition="Custom",
        WFImageX="32", WFImageY="0", WFImageWidth=text(("var", "BgW")), WFImageHeight=text(("var", "BgH")),
        WFRotation="0", WFOverlayImageOpacity="50"),
    setvar("Soft"),
    act("is.workflow.actions.overlayimageonimage", WFInput=var("Soft"), WFImage=var("Soft"),
        WFShouldShowImageEditor=False, WFImagePosition="Custom",
        WFImageX="0", WFImageY="8", WFImageWidth=text(("var", "BgW")), WFImageHeight=text(("var", "BgH")),
        WFRotation="0", WFOverlayImageOpacity="50"),
    setvar("Soft"),
    act("is.workflow.actions.overlayimageonimage", WFInput=var("Soft"), WFImage=var("Soft"),
        WFShouldShowImageEditor=False, WFImagePosition="Custom",
        WFImageX="0", WFImageY="16", WFImageWidth=text(("var", "BgW")), WFImageHeight=text(("var", "BgH")),
        WFRotation="0", WFOverlayImageOpacity="50"),
    setvar("Soft"),
    act("is.workflow.actions.overlayimageonimage", WFInput=var("Soft"), WFImage=var("Soft"),
        WFShouldShowImageEditor=False, WFImagePosition="Custom",
        WFImageX="0", WFImageY="32", WFImageWidth=text(("var", "BgW")), WFImageHeight=text(("var", "BgH")),
        WFRotation="0", WFOverlayImageOpacity="50"),
    setvar("Soft"),
    act("is.workflow.actions.image.crop", WFInput=var("Soft"), WFImageCropPosition="Center",
        WFImageCropWidth=text(("var", "W")), WFImageCropHeight=text(("var", "H"))),
    setvar("BgBlur"),
    act("is.workflow.actions.overlayimageonimage", WFInput=var("BgBlur"), WFImage=var("DimImage"),
        WFShouldShowImageEditor=False, WFImagePosition="Custom",
        WFImageX="0", WFImageY="0", WFImageWidth=text(("var", "W")), WFImageHeight=text(("var", "H")),
        WFRotation="0", WFOverlayImageOpacity="60"),
    setvar("Bg"),
    act("is.workflow.actions.image.resize", WFImage=var("Sdr"), WFInput=var("Sdr"),
        WFImageResizeWidth="Auto", WFImageResizeHeight=text(("var", "H"))),
    setvar("Main"),
    act("is.workflow.actions.properties.images", WFInput=var("Main"), WFContentItemPropertyName="Width"),
    setvar("MainW"),
    act("is.workflow.actions.math", WFInput=var("W"), WFMathOperation="-", WFMathOperand=text(("var", "MainW"))),
    setvar("Gap"),
    act("is.workflow.actions.math", WFInput=var("Gap"), WFMathOperation="\u00f7", WFMathOperand=2),
    act("is.workflow.actions.round", WFRoundTo="Ones Place", WFRoundMode="Normal"),
    setvar("MX"),
    act("is.workflow.actions.overlayimageonimage", WFInput=var("Bg"), WFImage=var("Main"),
        WFShouldShowImageEditor=False, WFImagePosition="Custom",
        WFImageX=text(("var", "MX")), WFImageY="0",
        WFImageWidth=text(("var", "MainW")), WFImageHeight=text(("var", "H")),
        WFRotation="0", WFOverlayImageOpacity="100"),
    setvar("Cropped"),
    act("is.workflow.actions.conditional", GroupingIdentifier=ORIENT, WFControlFlowMode=1),
    # HORIZONTAL: fit to width, then the five crop options
    act("is.workflow.actions.image.resize", WFImage=var("Sdr"), WFInput=var("Sdr"),
        WFImageResizeWidth=text(("var", "W")), WFImageResizeHeight="Auto"),
    setvar("Scaled"),
    # --- five crop candidates from top to bottom; the user picks one by thumbnail ---
    act("is.workflow.actions.properties.images", WFInput=var("Scaled"), WFContentItemPropertyName="Height"),
    setvar("ScaledH"),
    act("is.workflow.actions.math", WFInput=var("ScaledH"), WFMathOperation="-", WFMathOperand=text(("var", "H"))),
    setvar("Extra"),
    # darken the whole photo once; each option lays its crop back on top at full brightness
    act("is.workflow.actions.overlayimageonimage", WFInput=var("Scaled"), WFImage=var("DimImage"),
            WFShouldShowImageEditor=False, WFImagePosition="Custom",
            WFImageX="0", WFImageY="0", WFImageWidth=text(("var", "W")), WFImageHeight=text(("var", "ScaledH")),
            WFRotation="0", WFOverlayImageOpacity="100"),
    setvar("Dimmed"),
]
for i, frac in enumerate([0, 0.25, 0.5, 0.75, 1.0], start=1):
    actions += [
        act("is.workflow.actions.math", WFInput=var("Extra"), WFMathOperation="×", WFMathOperand=frac),
        act("is.workflow.actions.round", WFRoundTo="Ones Place", WFRoundMode="Normal"),
        setvar("OffY"),
        act("is.workflow.actions.image.crop", WFInput=var("Scaled"), WFImageCropPosition="Custom",
            WFImageCropX="0", WFImageCropY=text(("var", "OffY")),
            WFImageCropWidth=text(("var", "W")), WFImageCropHeight=text(("var", "H"))),
        setvar("Piece"),
        act("is.workflow.actions.overlayimageonimage", WFInput=var("Dimmed"), WFImage=var("Piece"),
            WFShouldShowImageEditor=False, WFImagePosition="Custom",
            WFImageX="0", WFImageY=text(("var", "OffY")), WFImageWidth=text(("var", "W")), WFImageHeight=text(("var", "H")),
            WFRotation="0", WFOverlayImageOpacity="100"),
        setvar("Preview"),
        # tag the option in the image itself: option i is i pixels narrower than the window.
        # (Names don't survive Choose from List; pixel sizes do.)
        act("is.workflow.actions.math", WFInput=var("W"), WFMathOperation="-", WFMathOperand=i),
        setvar("PW"),
        act("is.workflow.actions.image.resize", WFImage=var("Preview"), WFInput=var("Preview"),
            WFImageResizeWidth=text(("var", "PW")), WFImageResizeHeight="Auto"),
        act("is.workflow.actions.setitemname", WFName=f"Option {i}", WFDontIncludeFileExtension=False),
        setvar("Candidate"),
        setvar("Choices", var("Candidate")) if i == 1 else
        act("is.workflow.actions.appendvariable", WFInput=var("Candidate"), WFVariableName="Choices"),
    ]
actions += [
    act("is.workflow.actions.choosefromlist", WFInput=var("Choices"),
        WFChooseFromListActionPrompt="Pick the crop that fits best"),
    setvar("Chosen"),
    act("is.workflow.actions.properties.images", WFInput=var("Chosen"), WFContentItemPropertyName="Width"),
    setvar("ChosenW"),
    act("is.workflow.actions.math", WFInput=var("W"), WFMathOperation="-", WFMathOperand=text(("var", "ChosenW"))),
    setvar("Idx"),
    act("is.workflow.actions.math", WFInput=var("Idx"), WFMathOperation="-", WFMathOperand=1),
    setvar("Step"),
    act("is.workflow.actions.math", WFInput=var("Step"), WFMathOperation="\u00d7", WFMathOperand=text(("var", "Extra"))),
    setvar("Scaled4"),
    act("is.workflow.actions.math", WFInput=var("Scaled4"), WFMathOperation="\u00f7", WFMathOperand=4),
    act("is.workflow.actions.round", WFRoundTo="Ones Place", WFRoundMode="Normal"),
    setvar("FinalY"),
    act("is.workflow.actions.image.crop", WFInput=var("Scaled"), WFImageCropPosition="Custom",
        WFImageCropX="0", WFImageCropY=text(("var", "FinalY")),
        WFImageCropWidth=text(("var", "W")), WFImageCropHeight=text(("var", "H"))),
    setvar("Cropped"),
    act("is.workflow.actions.conditional", GroupingIdentifier=ORIENT, WFControlFlowMode=2),
    act("is.workflow.actions.overlayimageonimage", WFInput=var("FrameImage"), WFImage=var("Cropped"),
        WFShouldShowImageEditor=False, WFImagePosition="Custom",
        WFImageX=text(("var", "X")), WFImageY=text(("var", "Y")),
        WFImageWidth=text(("var", "W")), WFImageHeight=text(("var", "H")),
        WFRotation="0", WFOverlayImageOpacity="100"),
    setvar("Framed"),
    act("is.workflow.actions.overlayimageonimage", WFInput=var("Framed"), WFImage=var("FrameImage"),
        WFShouldShowImageEditor=False, WFImagePosition="Custom",
        WFImageX="0", WFImageY="0", WFImageWidth=str(CANVAS_W), WFImageHeight=str(CANVAS_H),
        WFRotation="0", WFOverlayImageOpacity="100"),
    setvar("Finished"),
    act("is.workflow.actions.image.convert", WFInput=var("Finished"), WFImageFormat="JPEG",
        WFImageCompressionQuality=0.9, WFImagePreserveMetadata=False),
    setvar("Jpeg"),
    act("is.workflow.actions.setitemname", WFInput=var("Jpeg"),
        WFName=text("TVArt-", ("var", "FrameId")), WFDontIncludeFileExtension=False),
    setvar("Named"),
    act("is.workflow.actions.appendvariable", WFInput=var("Named"), WFVariableName="Results"),
]
actions += [act("is.workflow.actions.repeat.each", GroupingIdentifier=grp, WFControlFlowMode=2)]
# 6. hand back
actions += [act("is.workflow.actions.previewdocument", WFInput=var("Results"))]
# 7. optional save; using the shortcut's own save step makes iOS ask for Photos permission the first time
actions += [act("is.workflow.actions.gettext", WFTextActionText="Save to Photos\nDone"),
            act("is.workflow.actions.text.split", WFTextSeparator="New Lines"),
            setvar("FinishOptions"),
            act("is.workflow.actions.choosefromlist", WFInput=var("FinishOptions"),
                WFChooseFromListActionPrompt="Save the framed images to Photos?"),
            setvar("Finish")]
ifg = str(uuid.uuid4()).upper()
actions += [act("is.workflow.actions.conditional", WFInput={"Type": "Variable", "Variable": var("Finish")},
                WFCondition=4, WFConditionalActionString="Save to Photos",
                GroupingIdentifier=ifg, WFControlFlowMode=0),
            act("is.workflow.actions.savetocameraroll", WFInput=var("Results")),
            act("is.workflow.actions.conditional", GroupingIdentifier=ifg, WFControlFlowMode=2)]

# Wire every "Set variable" without an explicit input to the previous action's output.
for i, a in enumerate(actions):
    p = a["WFWorkflowActionParameters"]
    if a["WFWorkflowActionIdentifier"] in ("is.workflow.actions.setvariable", "is.workflow.actions.round",
                                           "is.workflow.actions.setitemname", "is.workflow.actions.text.replace",
                                           "is.workflow.actions.text.split") and "WFInput" not in p:
        prev = actions[i - 1]["WFWorkflowActionParameters"]
        prev.setdefault("UUID", str(uuid.uuid4()).upper())
        p["WFInput"] = {"Value": {"Type": "ActionOutput", "OutputUUID": prev["UUID"],
                                  "OutputName": p.get("WFVariableName", "Result")},
                        "WFSerializationType": "WFTextTokenAttachment"}

wf = {
    "WFWorkflowActions": actions,
    "WFWorkflowClientVersion": "2605.0.5",
    "WFWorkflowMinimumClientVersion": 900,
    "WFWorkflowMinimumClientVersionString": "900",
    "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4292093695, "WFWorkflowIconGlyphNumber": 59784},  # green, "picture",
    "WFWorkflowImportQuestions": [],
    "WFWorkflowInputContentItemClasses": ["WFImageContentItem"],
    "WFWorkflowTypes": ["NCWidget", "WatchKit"],
    "WFWorkflowHasShortcutInputVariables": False,
    "WFQuickActionSurfaces": [],
}
with open("Wall Art.unsigned.shortcut", "wb") as fh:
    plistlib.dump(wf, fh, fmt=plistlib.FMT_BINARY)
print(len(actions), "actions")
