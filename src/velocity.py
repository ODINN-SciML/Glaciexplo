from oggm.shop import millan22
import pandas as pd


def add_velocity_data(gdirs, error=False):

    for gdir in gdirs:
        try:
            millan22.velocity_to_gdir(gdir, add_error=error)
        except Exception as e:
            print(f"Error occurred while processing {gdir.rgi_id}: {e}")


def get_velocity_statistics(gdirs):

    df_vel = millan22.compile_millan_statistics(gdirs)
    return df_vel


def create_df_velocity_errors(gdirs):
    df_vel = get_velocity_statistics(gdirs)
    df_vel_errors = pd.DataFrame()
    df_vel_errors["velocity_avg_error"] = df_vel[["millan_avg_err_vel"]]
    df_vel_errors["RGIId"] = df_vel.index
    df_vel_errors = df_vel_errors.reset_index(drop=True)
    return df_vel_errors
