import pandas as pd


def ensure_datetime(df, columns):
    output = df.copy()
    for column in columns:
        if column in output.columns:
            output[column] = pd.to_datetime(output[column], errors="coerce")
    return output


def summarize_dataframe(df, name):
    missing_values = int(df.isna().sum().sum())
    column_list = ", ".join(df.columns)
    return (
        f"{name}: {len(df)} rows, {len(df.columns)} columns, "
        f"{missing_values} missing values. Columns: {column_list}"
    )
