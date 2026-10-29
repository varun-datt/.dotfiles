import unittest

import sweep


class Leftovers(unittest.TestCase):
    def test_orphans_inside_the_worktree_and_orphan_yes_anywhere(self):
        procs = {10: (1, '/usr/bin/yes'), 11: (1, 'node'), 12: (500, 'node'), 13: (1, 'node'),
                 14: (1, '/Applications/Code'), 15: (1, 'vite'), 16: (77, '/usr/bin/yes')}
        dirs = {10: '/Users/x', 11: '/wt/a/sub', 12: '/wt/a', 13: '/wt/ab', 14: '/', 15: '/wt/a'}
        self.assertEqual([p for p, _, _ in sweep.leftovers('/wt/a', procs, dirs)], [10, 11, 15])

    def test_a_process_with_no_known_folder_is_left_alone_unless_it_is_yes(self):
        procs = {20: (1, 'node'), 21: (1, 'yes')}
        self.assertEqual([p for p, _, _ in sweep.leftovers('/wt/a', procs, {})], [21])


class Load(unittest.TestCase):
    def test_any_yes_holds_the_launch(self):
        self.assertIn('yes', sweep.load_reason({5: (300, '/usr/bin/yes')}, 0))

    def test_rising_swapouts_hold_the_launch(self):
        self.assertIn('swapping', sweep.load_reason({}, sweep.SWAP_PAGES + 1))

    def test_a_quiet_machine_passes(self):
        self.assertIsNone(sweep.load_reason({1: (0, 'launchd')}, sweep.SWAP_PAGES))


if __name__ == '__main__':
    unittest.main()
