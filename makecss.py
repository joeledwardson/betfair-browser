import sass
from myutils import dashutilities
from os import path, chdir
import mybrowser

chdir('mybrowser')
sass.compile(dirname=('scss', 'assets'))

sass.compile(
    dirname=(
        path.join(dashutilities.__path__[0], 'scss'),
        'assets'
    ),
    include_paths=[
        path.join(mybrowser.__path__[0], 'bootstrap', 'scss')
    ]
)