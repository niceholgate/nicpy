import pytest
from pathlib import Path
from definitions import TEST_DATA_DIR
from SearchInFiles import SearchInFiles

TEST_DATA_DIR_PATH = Path(TEST_DATA_DIR) / 'SearchInFiles'

# TODO: there are a lot of possible tests, just add them as use cases arise
# TODO: case_sensitive, whole_phrase_only can be tested in the nic_str method

def test_search_in_plaintexts():

    cat = 'plaintext'
    for file_type in SearchInFiles.known_types[cat]:
        # skip .py because these would get picked up by the test engine and also show errors in compiler
        if file_type != '.py':
            file1 = 'test_1{}'.format(file_type)
            file2 = 'test_2{}'.format(file_type)
            #                                                                                       1.1, 1.3    2.1 only  none  1.3, 2.1
            results = SearchInFiles(search_root_directory=str(TEST_DATA_DIR_PATH), search_strings=['cat jumped', 'hat ', 'pat', 'line'],
                                   requested_types=[file_type],
                                   case_sensitive=True, whole_phrase_only=False, search_in_doc_images=False).results

            assert len(results['files_to_search_inside'][cat]) == 2
            assert len(results['failed_file_paths'][cat]) == 0

            assert results['containing_file_paths']['cat jumped'][cat][str(TEST_DATA_DIR_PATH / file1)] == [1, 3]
            assert str(TEST_DATA_DIR_PATH / file2) not in results['containing_file_paths']['cat jumped'][cat].keys()

            assert str(TEST_DATA_DIR_PATH / file1) not in results['containing_file_paths']['hat '][cat].keys()
            assert results['containing_file_paths']['hat '][cat][str(TEST_DATA_DIR_PATH / file2)] == [1]

            assert str(TEST_DATA_DIR_PATH / file1) not in results['containing_file_paths']['pat'][cat].keys()
            assert str(TEST_DATA_DIR_PATH / file2) not in results['containing_file_paths']['pat'][cat].keys()

            assert results['containing_file_paths']['line'][cat][str(TEST_DATA_DIR_PATH / file1)] == [3]
            assert results['containing_file_paths']['line'][cat][str(TEST_DATA_DIR_PATH / file2)] == [1]

def test_search_in_presentations():

    cat = 'presentation'
    file_type = '.pptx'
    file1 = 'test_1{}'.format(file_type)
    file2 = 'test_2{}'.format(file_type)
    #
    results = SearchInFiles(search_root_directory=str(TEST_DATA_DIR_PATH), search_strings=['cat jumped', # 1.1 Paragraph 2, 2 occurrences, 1.3 Paragraph 1, 1 occurrence
                                                                                           'hat ',       # 2.1 Paragraph 1, 1 occurrence
                                                                                           'pat',        # None
                                                                                           'line'],      # 2.1 Paragraph 1, 1 occurrence, 1.3 Paragraph 1, 1 occurrence, 1.3 Paragraph 2, 1 occurrence
                           requested_types=[file_type],
                           case_sensitive=True, whole_phrase_only=False, search_in_doc_images=False).results

    assert len(results['files_to_search_inside'][cat]) == 2
    assert len(results['failed_file_paths'][cat]) == 0

    assert 'Object 2, Paragraph 2, 2 occurrences' in results['containing_file_paths']['cat jumped'][cat][str(TEST_DATA_DIR_PATH / file1)]['Slide 1']
    assert 'Object 2, Paragraph 1, 1 occurrence' in results['containing_file_paths']['cat jumped'][cat][str(TEST_DATA_DIR_PATH / file1)]['Slide 3']
    assert str(TEST_DATA_DIR_PATH / file2) not in results['containing_file_paths']['cat jumped'][cat].keys()

    assert str(TEST_DATA_DIR_PATH / file1) not in results['containing_file_paths']['hat '][cat].keys()
    assert 'Object 2, Paragraph 1, 1 occurrence' in results['containing_file_paths']['hat '][cat][str(TEST_DATA_DIR_PATH / file2)]['Slide 1']

    assert str(TEST_DATA_DIR_PATH / file1) not in results['containing_file_paths']['pat'][cat].keys()
    assert str(TEST_DATA_DIR_PATH / file2) not in results['containing_file_paths']['pat'][cat].keys()

    assert 'Object 2, Paragraph 1, 1 occurrence' in results['containing_file_paths']['line'][cat][str(TEST_DATA_DIR_PATH / file2)]['Slide 1']
    assert 'Object 2, Paragraph 1, 1 occurrence' in results['containing_file_paths']['line'][cat][str(TEST_DATA_DIR_PATH / file1)]['Slide 3']
    assert 'Object 2, Paragraph 2, 1 occurrence' in results['containing_file_paths']['line'][cat][str(TEST_DATA_DIR_PATH / file1)]['Slide 3']
