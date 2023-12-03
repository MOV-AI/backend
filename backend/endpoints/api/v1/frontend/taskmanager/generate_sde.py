"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential
   Developers:
   - Pedro Cristóvão (pedro.cristovao@mov.ai)
   - Mithun Kinarullathil (mithun@mov.ai)
   - Daniel Gonçalves (daniel.goncalves@mov.ai)

   v.2.0
"""
from movai_core_shared.common.utils import is_enterprise
from movai_core_shared.logger import Log


LOGGER = Log.get_logger(__name__)

from dal.models.scopestree import ScopesTree

try:
    from movai_core_enterprise.scopes.shareddataentry import SharedDataEntry
except ImportError:
    LOGGER.warning("movai_core_enterprise is not installed.")


def get_falsy_values(data_type="str"):
    """
    Returns default value for each data type
    """
    type2value = {"str": "", "num": 0, "int": 0, "bool": False, "array": []}
    if data_type in type2value:
        return type2value[data_type]
    else:
        return ""

def get_default_values(field):
    """
    Returns default values of a field
    """
    if "Default" in field:
        return {"Value": field.Default}
    return {"Value": get_falsy_values(field.Type if "Type" in field else "str")}


def get_entry(template, option_index):
    """
    Function that generates a shared data entry based on a template and a integer number
    """

    # entry to be filled
    entry = {"id": "", "name": "", "obj": template.serialize()}
    for k in list(template.Field):
        options = get_options_from_template_field(template, k)
        entry["id"] = f"{template.Label}_opt{option_index}"
        entry["name"] = entry["id"]
        entry["obj"]["Label"] = entry["id"]
        entry["obj"]["TemplateID"] = template.Label
        if option_index < len(options):
            entry["obj"]["Field"][k] = {"Value": options[option_index]}
        else:
            entry["obj"]["Field"][k] = get_default_values(template.Field[k])
    return entry


def get_options_from_template_field(template, field):
    """
    Returns values of a particular field of a template
    """
    result = []
    if (
        "Field" in template
        and field in template.Field
        and "Options" in template.Field[field]
        and template.Field[field].Options is not None
    ):
        for option in list(template.Field[field].Options):
            if template.Field[field].Type == "bool":
                result.append(template.Field[field].Default)
            else:
                result.append(option["label"])
    return result


def get_templates():
    """
    Returns list of all templates
    """
    return [
        ScopesTree()().SharedDataTemplate[x["ref"]]
        for x in ScopesTree()().list_scopes(scope="SharedDataTemplate")
    ]


def save_entry(entry):
    """
    warning: super hack below, please revise.

    Creates and saves an entry in database
    """
    obj = entry["obj"]
    try:
        if is_enterprise:
            s = SharedDataEntry(entry["id"], templateid=entry["obj"]["TemplateID"], new=True)
            s.Label = obj["Label"]
            s.Description = obj["Description"] if "Description" in obj else ""
            also_s = ScopesTree()().SharedDataEntry[entry["id"]]
            for k in obj["Field"]:
                also_s.Field[k] = obj["Field"][k]
            also_s.write()
        else:
            LOGGER.error("cannot save SharedDataEntry because movai_core_enterprise is not installed.")
    except Exception as e:
        LOGGER.warn(f"Caught Exception while creating {entry['id']}: {str(e)}")

def get_max_options_number(template):
    """
    Returns max number of values of each property of the template
    """
    max_option_number = 0
    for k in list(template.Field):
        if template.Field[k].Options is not None and template.Field[k].Type != "bool":
            max_option_number = max(max_option_number, len(list(template.Field[k].Options)))
    return max_option_number

def gen_shared_data_entries(**kwargs):
    """
    Stateful function that generates share data entries in database
    """
    entries = []
    # for each template and max atribute value
    for template in get_templates():
        max_options_number = max(get_max_options_number(template), 1)
        for i in range(max_options_number):
            entry = get_entry(template, i)
            # entries.append(entry)
            save_entry(entry)
    return entries
