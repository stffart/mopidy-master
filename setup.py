from setuptools import setup

from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()
setup(
    name='mopidy-master',
    version='1.0',
    description='Mopidy extension to translate music from different sources to satellites',
    description_file='README.md',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/stffart/mopidy-master',
    author='stffart',
    author_email='stffart@gmail.com',
    license='GPLv3',
    packages=['mopidy_master'],
    package_dir={'mopidy_master':'mopidy_master'},
    package_data={'mopidy_master':['ext.conf']},
    install_requires=[],
    entry_points={
        'mopidy.ext': [
            'master = mopidy_master:Extension',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
    ],
)

