from typing import List, Dict
import argparse
import datetime
import logging
import os
import re
import sys
import time

StatDataType = Dict[str, Dict[str, List[int]]]

logger = logging.getLogger(__name__)


class DailyStatGenerator:
    """Generates timeseries data on Covid-19 daily new cases in Tokyo areas.

    The source csv data can be retrieved from
    https://github.com/smatsumt/parse-tokyo-covid-report-pdf/csv
    """
    def __init__(self) -> None:
        self.min_date = None
        self.stat_data = {}
        self.area_list = []

    def load_cache(self, cache_file: str) -> bool:
        try:
            with open(cache_file, 'r') as f:
                min_date_obj = None
                for line in f:
                    line = line.strip()
                    try:
                        (date, area, total, new) = line.split(',')
                        d = datetime.date.fromisoformat(date)
                        if min_date_obj is None or d < min_date_obj:
                            min_date_obj = d
                        total = int(total)
                        new = int(new)
                    except ValueError as e:
                        logger.debug('Skipping line "%s": %s', line, e)
                        continue
                    self.stat_data.setdefault(date, {})[area] = [total, new]
                self.min_date = min_date_obj.isoformat()
                return True
        except OSError as e:
            logger.error(e)
            return False

    def _fix_prevdays(self, start_date: str, area: str, total: int) -> None:
        date = start_date
        dobj = datetime.date.fromisoformat(start_date)
        oneday = datetime.timedelta(days=1)
        while date in self.stat_data and area in self.stat_data[
                date] and self.stat_data[date][area][0] > total:
            new = self.stat_data[date][area][1] - (
                self.stat_data[date][area][0] - total)
            if new < 0:
                new = 0
            self.stat_data[date][area] = [total, new]
            dobj = dobj - oneday
            date = dobj.isoformat()

    def generate_from_file(self, date: str, filename: str) -> None:
        if len(self.stat_data) == 0:
            self.min_date = date
        prev_day = (datetime.date.fromisoformat(date) -
                    datetime.timedelta(days=1)).isoformat()
        is_1st_day = date == self.min_date
        if not is_1st_day and prev_day not in self.stat_data:
            logger.error(
                'cannot calculate values for %s as data for %s not found',
                date, prev_day)
            return
        prevday_data = {} if is_1st_day else self.stat_data[prev_day]
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    try:
                        (area, total) = line.split(',')
                        total = int(total)
                    except ValueError as e:
                        logger.error('"%s": %s', line, e)
                        continue
                    if area.startswith('調査中'):
                        continue
                    if is_1st_day:
                        self.area_list.append(area)
                    new = total - prevday_data.setdefault(area, [0])[0]
                    if new < 0:
                        new = 0
                        # Not sure if adjustment here makes sense.
                        self._fix_prevdays(prev_day, area, total)
                    self.stat_data.setdefault(date, {})[area] = [total, new]
        except OSError as e:
            logger.error(e)
            return

    def generate_from_dir(self, csv_dir: str) -> 'DailyStatGenerator':
        if not os.path.isdir(csv_dir):
            logger.error('%s is not a directory', csv_dir)
            return
        r = re.compile(r'^(\d{8}).csv$')
        for filename in sorted(os.listdir(csv_dir)):
            filepath = os.path.join(csv_dir, filename)
            logger.info('Processsing %s', filepath)
            m = r.match(filename)
            try:
                if m is None or m.group(1) in self.stat_data:
                    raise ValueError
                t = time.strptime(m.group(1), '%Y%m%d')
                # date is in iso format.
                date = '%04d-%02d-%02d' % (t.tm_year, t.tm_mon, t.tm_mday)
            except ValueError:
                logger.debug('Skipping %s', filepath)
                continue
            if date in self.stat_data:
                logger.info('Skipping %s as data already exists', filepath)
            else:
                self.generate_from_file(date, filepath)

        if self.min_date is not None:
            # Delete the oldest data as it is an accumlated nunmber.
            del self.stat_data[self.min_date]
        return self

    def to_csvfile(self, output_file: str) -> None:
        if output_file is None:
            f = sys.stdout
        else:
            try:
                f = open(output_file, 'w')
            except OSError as e:
                logger.error(e)
                return
        try:
            f.write('Date,Area,Total Cases,New Cases\n')
            for date in sorted(self.stat_data.keys()):
                st = self.stat_data[date]
                for area in self.area_list:
                    f.write('%s,%s,%d,%d\n' % (date, area, *st[area]))
        except OSError as e:
            logger.error(e)
            return
        finally:
            if f != sys.stdout:
                f.close()


def main():
    logging.basicConfig(format='%(asctime)-15s %(levelname)-9s %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action='count', default=0)
    parser.add_argument(
        '--output_file',
        '-o',
        default=None,
        help=
        'path to output file. Used as cache if exists and cache file is unspecified.'
    )
    parser.add_argument('--cache_file',
                        '-c',
                        default=None,
                        help='path to cache file.')
    parser.add_argument(
        'csv_dir',
        help='path to the directory where daily csv files are stored.')
    args = parser.parse_args()

    if args.verbose > 0:
        logger.setLevel(logging.INFO if args.verbose == 1 else logging.DEBUG)

    generator = DailyStatGenerator()

    def load_cache(filename: str) -> bool:
        logger.info('Loading %s as cache', filename)
        generator.load_cache(filename)

    # Load cache file if exists first, then try output file if exists.
    if args.cache_file is not None:
        if not load_cache(args.cache_file):
            if args.output_file is not None:
                load_cache(args.output_file)

    logger.info('Generating daily stat from %s', args.csv_dir)
    generator.generate_from_dir(args.csv_dir).to_csvfile(args.output_file)


if __name__ == '__main__':
    main()
