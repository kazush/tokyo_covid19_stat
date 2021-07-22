from typing import List
import argparse
import chart_studio.plotly as py
import plotly.express as px
import pandas as pd

CSV_URL = 'https://stopcovid19.metro.tokyo.lg.jp/data/130001_tokyo_covid19_patients.csv'


class TokyoCovid19Stat:
    """Holds Tokyo Covid-19 stat data."""

    AGECOLNAME_MAP = {
        '10歳未満': 'Under10',
        '10代': '10s',
        '20代': '20s',
        '30代': '30s',
        '40代': '40s',
        '50代': '50s',
        '60代': '60s',
        '70代': '70s',
        '80代': '80s',
        '90代': '90s',
        '100歳以上': '100andOver',
        '不明': 'Unknown'
    }

    AGECOLNAMES = ['Under10'] + ['%s0s' % i for i in range(1, 10)
                                 ] + ['100andOver', 'Unknown']

    def __init__(self, csv_file_path: str = None):
        self.csv_file_path = CSV_URL if csv_file_path is None else csv_file_path
        self._df = None

    def update(self) -> None:
        df = pd.read_csv(self.csv_file_path,
                         parse_dates=['公表_年月日'],
                         index_col='公表_年月日')
        df['患者_年代'].replace({"'-": '不明'}, inplace=True)
        self._df = df

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            self.update()
        return self._df

    @property
    def cases_by_age(self) -> pd.DataFrame:
        df = pd.crosstab(self.df.index, self.df['患者_年代'])
        df.rename(columns=self.AGECOLNAME_MAP, inplace=True)
        df.index.names = ['Date']
        df.columns.name = 'Age'
        return df[TokyoCovid19Stat.AGECOLNAMES]  # sort columns

    @property
    def cases(self) -> pd.DataFrame:
        return pd.DataFrame({'Cases': self.cases_by_age.sum(axis=1)})


def sma(df: pd.DataFrame, days: int = 7) -> pd.DataFrame:
    return df.rolling(days).mean()


def with_date(orig_df: pd.DataFrame) -> pd.DataFrame:
    df = orig_df.copy()
    df['Date'] = df.index.to_list()
    return df


def melt(orig_df: pd.DataFrame,
         value_columns: List[str],
         var_name: str,
         value_name: str = 'Cases') -> pd.DataFrame:
    """Unpivot the given DataFrame to be used with Plotly."""
    df = with_date(orig_df)
    df = df[['Date'] + value_columns]
    return df.melt(id_vars=['Date'],
                   value_vars=value_columns,
                   var_name=var_name,
                   value_name=value_name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv_file_path')
    args = parser.parse_args()

    st = TokyoCovid19Stat(args.csv_file_path)

    cases_by_age = melt(st.cases_by_age,
                        value_columns=TokyoCovid19Stat.AGECOLNAMES,
                        var_name='Age')

    sma_by_age = melt(sma(st.cases_by_age),
                      value_columns=TokyoCovid19Stat.AGECOLNAMES,
                      var_name='Age')

    title = 'Tokyo Covid-19 New Cases By Age'
    fig = px.area(cases_by_age, x='Date', y='Cases', color='Age', title=title)
    py.plot(fig, filename=title, auto_open=False)

    title = 'Tokyo Covid-19 New Cases 7-day Moving Average By Age'
    fig = px.line(sma_by_age, x='Date', y='Cases', color='Age', title=title)
    fig.add_bar(x=st.cases.index,
                y=st.cases['Cases'],
                name='Raw Total',
                marker=dict(color='gray'))
    py.plot(fig, filename=title, auto_open=False)


if __name__ == '__main__':
    main()
