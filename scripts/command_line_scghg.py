import inquirer
from pathlib import Path
from pyfiglet import Figlet
import os
import yaml
import sys

from scghg_utils import read_replace_conf, epa_scghgs, VERSION

if __name__ == "__main__":

    f = Figlet(font="slant", width=100)
    print(f.renderText("DSCIM"))
    print(f"... dscim-facts-epa version {VERSION} ...")

    # Path to the config for this run
    config = 'configs/master_conf.yaml'
    with open(config) as stream:
        conf = yaml.safe_load(stream)

    coastal_v = str(conf["coastal_version"])
    mortality_v = str(conf["mortality_version"])
    CAMEL_v = f"CAMEL_m{mortality_v}_c{coastal_v}"

    pulse_years = [2020, 2030]
    pulse_year_choices = [(str(i), i) for i in pulse_years]
    questions = [
        inquirer.Checkbox(
            "menu_option",
            message="Select risk type (If choosing Risk Neutral, the only available sector is Combined)",
            choices=[
                ("Risk Neutral", "risk_neutral"),
            ],
            default=[
                "risk_neutral",
            ],
        ),
        inquirer.Checkbox(
            "sector",
            message="Select sector",
            choices=[
                ("Combined", CAMEL_v),
                ("Coastal", "coastal_v" + coastal_v),
                ("Agriculture", "agriculture"),
                ("Mortality", "mortality_v" + mortality_v),
                ("Energy", "energy"),
                ("Labor", "labor"),
            ],
            default=[
                CAMEL_v,
                # "coastal_v" + coastal_v,
                # "agriculture",
                # "mortality_v" + mortality_v,
                # "energy",
                # "labor",
            ],
        ),
        inquirer.Checkbox(
            "eta_rhos",
            message="Select discount rates",
            choices=[
                ("Eta 1, Rho 0.0001", [1.0, 0.0001]),
            ],
            default=[
                [1.0, 0.0001],
            ],
        ),
        inquirer.Checkbox(
            "pulse_year",
            message="Select pulse years",
            choices=pulse_year_choices,
            default=pulse_years,
        ),
        inquirer.Checkbox(
            "U.S.",
            message="Select valuation type",
            choices=[("Global", False), ("Territorial U.S.", True)],
            default=[False, 
                    #  True
                     ],
        ),
        inquirer.Checkbox(
            "files",
            message="Optional files to save (will increase runtime substantially)",
            choices=[
                ("Global consumption no pulse", "gcnp"),
                ("Uncollapsed scghgs", "uncollapsed"),
            ],
        ),
    ]

    answers = inquirer.prompt(questions)
    eta_rhos = answers["eta_rhos"]
    sector = answers["sector"]
    menu_options = answers["menu_option"]
    pulse_years = answers["pulse_year"]
    terr_us_ls = answers["U.S."]
    gcnp = True if "gcnp" in answers["files"] else False
    uncollapsed = True if "uncollapsed" in answers["files"] else False

    coastal_v = str(conf["coastal_version"])
    mortality_v = str(conf["mortality_version"])
    CAMEL_v = f"CAMEL_m{mortality_v}_c{coastal_v}"

    gas_conversion_dict = {"CO2_Fossil": "CO2"}

    risk_combos = [[mo, "euler_ramsey"] for mo in menu_options]

    for terr_us in terr_us_ls:
        locale = "Territory US" if terr_us else "Global"
        print("=========================")
        print(f"Generating {locale} SCCs")
        print("=========================")
        print("")
        if terr_us:
            sector = [i + "_USA" for i in sector]
        epa_scghgs(
            sector,
            conf,
            config,
            gas_conversion_dict,
            terr_us,
            eta_rhos,
            risk_combos,
            pulse_years=pulse_years,
            gcnp=gcnp,
            uncollapsed=uncollapsed,
        )
    print(f"All results are available in {str(Path(conf['save_path']))}")
