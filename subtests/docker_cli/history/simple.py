"""
Test output of docker history command

Initialize
1. Make new image name.
2. Make changes in image by docker run [dockerand_data_prepare_cmd].
3. Make changes in image by docker run [dockerand_data_prepare_cmd].
4. Make changes in image by docker run [dockerand_data_prepare_cmd].
run_once
5. history changes.
postprocess
6. check if image history is correct.
clean
7. remote historyted image from local repo.
"""

from history import history_base

# Okay to be less-strict for these cautions/warnings in subtests
# pylint: disable=C0103,C0111,R0904,C0103


class simple(history_base):
    config_section = 'docker_cli/history/simple'
