import xarray as xr
import dscim
import yaml
from dscim.menu.simple_storage import Climate, EconVars
import pandas as pd
import numpy as np
from itertools import product
from pathlib import Path
import os
import re
import subprocess
from datetime import date
from dscim.menu.risk_aversion import RiskAversionRecipe
from dscim.menu.baseline import Baseline

# EDIT this line upon each release of dscim-facts-epa
VERSION = "0.1.0"

MENU_OPTIONS = {
    "adding_up": dscim.menu.baseline.Baseline,
    "risk_aversion": dscim.menu.risk_aversion.RiskAversionRecipe,
    "equity": dscim.menu.equity.EquityRecipe,
}

# For configs that are generated in the FACTS docker, file structure is relative to the docker paths.
# This function serves to ensure that configs generated in the FACTS docker have their filepaths
# converted to paths that are relative to this script
def read_replace_conf(master):
    try:
        with open(master, "r") as stream:
            docker_replace = stream.read().replace(
                "/opt/dscim-facts-epa", str(Path(os.getcwd()).parent.absolute())
            )
            conf = yaml.safe_load(docker_replace)
    except FileNotFoundError:
        raise FileNotFoundError(
            "Please run directory_setup.py or place the config in your current working directory"
        )
    return conf


def makedir(path):
    if not os.path.exists(path):
        os.makedirs(path)


# def generate_meta(
#     menu_item,
#     conf,
#     gas_conversion_dict,
#     terr_us,
# ):
#     # find machine name
#     machine_name = os.getenv("HOSTNAME")
#     if machine_name is None:
#         try:
#             machine_name = os.uname()[1]
#         except AttributeError:
#             machine_name = "unknown"

#     # find git commit hash
#     try:
#         gitlabel = (
#             subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
#             .decode("ascii")
#             .strip()
#         )
#     except subprocess.CalledProcessError:
#         gitlabel = "unknown"

#     meta = {
#         "Author": "Climate Impact Lab",
#         "Date Created": date.today().strftime("%d/%m/%Y"),
#         "Units": "2020 PPP-adjusted USD",
#     }

#     for attr_dict in [
#         vars(menu_item),
#         vars(vars(menu_item)["climate"]),
#         vars(vars(menu_item)["econ_vars"]),
#     ]:
#         meta.update(
#             {
#                 k: v
#                 for k, v in attr_dict.items()
#                 if (type(v) not in [xr.DataArray, xr.Dataset, pd.DataFrame])
#                 and k not in ["damage_function", "logger"]
#             }
#         )

#     # update with git hash and machine name
#     meta.update(
#         dict(
#             machine=machine_name,
#             commit=gitlabel,
#             url=f"https://github.com/ClimateImpactLab/dscim-facts-epa/commit/{gitlabel}",
#         )
#     )

#     # convert to strs
#     meta = {k: v if type(v) in [int, float] else str(v) for k, v in meta.items()}

#     # exclude irrelevant attrs
#     irrelevant_keys = [
#         "econ_vars",
#         "climate",
#         "subset_dict",
#         "filename_suffix",
#         "ext_subset_start_year",
#         "ext_subset_end_year",
#         "ext_end_year",
#         "ext_method",
#         "clip_gmsl",
#         "scenario_dimensions",
#         "scc_quantiles",
#         "quantreg_quantiles",
#         "quantreg_weights",
#         "full_uncertainty_quantiles",
#         "extrap_formula",
#         "fair_dims",
#         "sector_path",
#         "save_files",
#         "save_path",
#         "delta",
#         "histclim",
#         "ce_path",
#         "gmst_path",
#         "gmsl_path",
#     ]
#     for k in irrelevant_keys:
#         if k in meta.keys():
#             del meta[k]

#     # adjust attrs
#     meta["emission_scenarios"] = "RFF-SPv2"
#     meta["damagefunc_base_period"] = meta.pop("base_period")
#     meta["socioeconomics_path"] = meta.pop("path")
#     meta["gases"] = meta["gases"].split("'")
#     meta["gases"] = [e for e in meta["gases"] if e not in (", ", "[", "]")]
#     meta["gases"] = [gas_conversion_dict[gas] for gas in meta["gases"]]

#     if meta["sector"] == "CAMEL_m1_c0.20":
#         meta["sector"] = "combined"
#     else:
#         meta["sector"] = re.split("_", meta["sector"])[0]

#     if terr_us:
#         meta.update(
#             discounting_socioeconomics_path=f"{conf['rffdata']['socioec_output']}/rff_global_socioeconomics.nc4"
#         )

#     return meta


# # Merge attrs
# def merge_meta(attrs, meta):
#     if len(attrs) == 0:
#         attrs.update(meta)
#     else:
#         for meta_keys in attrs.keys():
#             if str(meta[meta_keys]) not in str(attrs[meta_keys]):
#                 if type(attrs[meta_keys]) != list:
#                     update = [attrs[meta_keys]]
#                     update.append(meta[meta_keys])
#                     attrs[meta_keys] = update
#                 else:
#                     attrs[meta_keys].append(meta[meta_keys])
#     return attrs


################################################################################


# Function for one run of SCGHGs
def epa_scghg(
    gas_conversion_dict,
    conf,
    sector="CAMEL_m1_c0.20",
    terr_us=False,
    eta=1.0,
    rho=0.0001,
    pulse_year=2020,
    discount_type="euler_ramsey",
    menu_option="risk_aversion",
):

    # Read in U.S. and global socioeconomic files
    if terr_us:
        econ = EconVars(path_econ=conf["econdata"]["USA_ssp"])
    else:
        econ = EconVars(path_econ=conf["econdata"]["global_ssp"])
        
    add_kwargs = {
        "econ_vars": econ,
        "climate_vars":  Climate(
                **conf[f"AR6_ssp_climate"],
                pulse_year=pulse_year,
                ecs_mask_name=None,
            ),
        "formula": conf["sectors"][sector if not terr_us else sector[:-4]]["formula"],
        "discounting_type": discount_type,
        "sector": sector,
        "ce_path":  f"{conf['paths']['reduced_damages_library']}/{sector}/",
        "save_path": None,
        "eta": eta,
        "rho": rho,
        "damage_function_path": f"{conf['paths']['ssp_damage_function_library']}/{sector}",
        "fair_dims": ["simulation"],
    }

    # Combine config kwargs with the add_kwargs for global discounting and damages
    kwargs_global = conf["global_parameters"].copy()
    for k, v in add_kwargs.items():
        assert (
            k not in kwargs_global.keys()
        ), f"{k} already set in config. Please check `global_parameters`."
        kwargs_global.update({k: v})

    if menu_option == "risk_aversion":
        menu_item = RiskAversionRecipe(**kwargs_global)
    elif menu_option == "risk_neutral":
        menu_item = Baseline(**kwargs_global)
    
    df = menu_item.uncollapsed_discount_factors
    md = menu_item.uncollapsed_marginal_damages

    # Compute SCGHGs
    # Multiplying marginal damages by discount factors and summing across years creates the SCGHGs
    scghgs = (
        md.rename(marginal_damages="scghg") * df.rename(discount_factor="scghg")
    ).sum("year")

    # Code to calculate epa-spec adjustment factors
    gcnp = menu_item.global_consumption_no_pulse.rename("gcnp")

    meta = {} # generate_meta(
    #     menu_item,
    #     conf,
    #     gas_conversion_dict,
    #     False,
    # )

    return [scghgs, gcnp, meta]


# Function to perform multiple runs of SCGHGs and combine into one file to save out
def epa_scghgs(
    sectors,
    conf,
    conf_name,
    gas_conversion_dict,
    terr_us,
    etas_rhos,
    risk_combos=(("adding_up", "euler_ramsey")),
    pulse_years=(2020, 2030, 2040, 2050, 2060, 2070, 2080),
    gcnp=False,
    uncollapsed=False,
):
    attrs = {}

    # Nested for loops to run each combination of SCGHGs requested
    # Each run of the outer loop saves one set of SCGHGs
    # The inner loop combines all SCGHG runs for that file
    for j, pulse_year in product(risk_combos, pulse_years):

        discount_type = j[1]
        menu_option = j[0]
        for sector in sectors:
            # These arrays will be populated with data arrays to be combined
            all_arrays_uscghg = []
            all_arrays_gcnp = []
            
            if re.split("_", sector)[0] == "CAMEL":
                sector_short = "combined"
            else:
                sector_short = re.split("_", sector)[0]

            for i in etas_rhos:

                eta = i[0]
                rho = i[1]

                print(
                    f"Calculating {'territorial U.S.' if terr_us else 'global'} {sector_short} scghgs {'and gcnp' if gcnp else ''} \n discount rate: {str(eta) + '_' + str(rho)} \n pulse year: {pulse_year}"
                )
                df_single_scghg, df_single_gcnp, meta = epa_scghg(
                    gas_conversion_dict,
                    conf,
                    sector=sector,
                    terr_us=terr_us,
                    discount_type=discount_type,
                    menu_option=menu_option,
                    eta=eta,
                    rho=rho,
                    pulse_year=pulse_year,
                )

                # Creates new coordinates to differentiate between runs
                # For SCGHGs
                df_scghg = df_single_scghg.assign_coords(
                    menu_option=menu_option,
                    sector=sector_short,
                )
                df_scghg_expanded = df_scghg.expand_dims(
                    ["menu_option", "sector"]
                )
                if "simulation" in df_scghg_expanded.dims:
                    df_scghg_expanded = df_scghg_expanded.drop_vars("simulation")
                all_arrays_uscghg = all_arrays_uscghg + [df_scghg_expanded]

                # For global consumption no pulse
                df_gcnp = df_single_gcnp.assign_coords(
                    menu_option=menu_option,
                    sector=sector_short,
                )
                df_gcnp_expanded = df_gcnp.expand_dims(
                    ["menu_option", "sector"]
                )
                if "simulation" in df_gcnp_expanded.dims:
                    df_gcnp_expanded = df_gcnp_expanded.drop_vars("simulation")
                all_arrays_gcnp = all_arrays_gcnp + [df_gcnp_expanded]

            # attrs = merge_meta(attrs, meta)

            print("Processing...")
            df_full_scghg = xr.combine_by_coords(all_arrays_uscghg)
            df_full_gcnp = xr.combine_by_coords(all_arrays_gcnp)

            # Changes coordinate names of gases
            df_full_scghg = df_full_scghg.assign_coords(
                gas=[gas_conversion_dict[gas] for gas in df_full_scghg.gas.values]
            )

            # Splits SCGHGs by gas and saves them out separately
            # For uncollapsed SCGHGs
            conf_savename = ""
            gases = ["CO2_Fossil"]
            if uncollapsed:
                for gas in gases:
                    out_dir = (
                        Path(conf["save_path"])
                        / f"{'territorial_us' if terr_us else 'global'}_scghgs"
                        / "full_distributions"
                        / gas
                    )
                    makedir(out_dir)
                    uncollapsed_gas_scghgs = (
                        df_full_scghg.sel(gas=gas_conversion_dict[gas], drop=True)
                        .to_dataframe()
                        .reindex()
                    )
                    print(
                        f"Saving {'territorial U.S.' if terr_us else 'global'} uncollapsed {sector_short} sc-{gas} \n pulse year: {pulse_year}"
                    )
                    uncollapsed_gas_scghgs.to_csv(
                        out_dir
                        / f"{conf_savename}sc-{gas}-dscim-{menu_option}-{sector_short}-{pulse_year}-n10000.csv"
                    )
                    # attrs_save = attrs.copy()
                    # attrs_save["gases"] = gas
                    # with open(
                    #     out_dir / f"{conf_savename}attributes-{gas}-{sector_short}.txt",
                    #     "w",
                    # ) as f:
                    #     for key, value in attrs_save.items():
                    #         f.write("%s:%s\n" % (key, value))

            # Applies the adjustment factor to convert to certainty equivalent SCGHGs
            df_full_scghg = (
                df_full_scghg.scghg
            ).mean(dim="simulation")

            # Splits and saves collapsed SCGHGs
            for gas in gases:
                out_dir = (
                    Path(conf["save_path"])
                    / f"{'territorial_us' if terr_us else 'global'}_scghgs"
                )

                makedir(out_dir)
                collapsed_gas_scghg = (
                    df_full_scghg.sel(gas=gas_conversion_dict[gas], drop=True)
                    .rename("scghg")
                    .to_dataframe()
                    .reindex()
                )
                print(
                    f"Saving {'territorial U.S.' if terr_us else 'global'} collapsed {sector_short} sc-{gas} \n pulse year: {pulse_year}"
                )
                collapsed_gas_scghg.to_csv(
                    out_dir
                    / f"{conf_savename}sc-{gas}-dscim-{menu_option}-{sector_short}-{pulse_year}.csv"
                )

            # Creates attribute files
            with open(
                out_dir / f"{conf_savename}attributes-{sector_short}.txt", "w"
            ) as f:
                for key, value in attrs.items():
                    f.write("%s:%s\n" % (key, value))

            # save global consumption no pulse for each sector. Does not vary by pulse_year
            if pulse_year == pulse_years[0]:
                # Fewer GCNPs are saved because they vary across fewer dimensions than SCGHGs
                if gcnp:
                    out_dir = Path(conf["save_path"]) / "gcnp"
                    makedir(out_dir)
                    df_full_gcnp.attrs = attrs
                    print(f"Saving {sector_short} global consumption no pulse (gcnp)")
                    df_full_gcnp.to_netcdf(
                        out_dir / f"{conf_savename}gcnp-dscim-{sector_short}.nc4"
                    )
                    print(f"gcnp is available in {str(out_dir)}")

    print(
        f"{'territorial_us' if terr_us else 'global'}_scghgs are available in {str(Path(conf['save_path']))}/{'territorial_us' if terr_us else 'global'}_scghgs"
    )
    if uncollapsed:
        print(
            f"Full distributions of {'territorial_us' if terr_us else 'global'}_scghgs are available in {str(Path(conf['save_path']))}/{'territorial_us' if terr_us else 'global'}_scghgs/full_distributions"
        )
