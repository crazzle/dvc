import os
from boto.s3.connection import S3Connection

from neatlynx.cmd_base import CmdBase, Logger
from neatlynx.exceptions import NeatLynxException
from neatlynx.data_file_obj import DataFileObjExisting


class DataRemoveError(NeatLynxException):
    def __init__(self, msg):
        NeatLynxException.__init__(self, 'Data remove error: {}'.format(msg))


class CmdDataRemove(CmdBase):
    def __init__(self):
        CmdBase.__init__(self)

        conn = S3Connection(self.config.aws_access_key_id, self.config.aws_secret_access_key)

        bucket_name = self.config.aws_storage_bucket
        self._bucket = conn.lookup(bucket_name)
        if not self._bucket:
            self._bucket = conn.create_bucket(bucket_name)
            Logger.info('S3 bucket "{}" was created'.format(bucket_name))
        pass

    def define_args(self, parser):
        self.add_string_arg(parser, 'target', 'Target to remove - file or directory')
        parser.add_argument('-r', '--recursive', action='store_true', help='Remove directory recursively')
        parser.add_argument('-k', '--keep-in-cloud', action='store_true', help='Keep file in cloud')
        pass

    def run(self):
        target = self.args.target

        if os.path.isdir(target):
            if not self.args.recursive:
                raise DataRemoveError('Directory cannot be removed. Use --recurcive flag.')

            if os.path.realpath(target) == \
                    os.path.realpath(os.path.join(self.git.git_dir_abs, self.config.data_dir)):
                raise DataRemoveError('data directory cannot be removed')

            return self.remove_dir(target)

        dobj = DataFileObjExisting(target, self.git, self.config)
        if os.path.islink(dobj.data_file_relative):
            return self.remove_symlink(dobj.data_file_relative)

        raise DataRemoveError('Cannot remove a regular file "{}"'.format(target))

    def remove_symlink(self, file):
        dobj = DataFileObjExisting(file, self.git, self.config)

        if os.path.isfile(dobj.cache_file_relative):
            os.remove(dobj.cache_file_relative)
            dobj.remove_cache_dir_if_empty()

        if os.path.isfile(dobj.state_file_relative):
            os.remove(dobj.state_file_relative)
            dobj.remove_state_dir_if_empty()

        if not self.args.keep_in_cloud:
            key = self._bucket.get_key(dobj.cache_file_aws_key)
            if not key:
                Logger.warn('S3 remove warning: file "{}" does not exist in S3'.format(dobj.cache_file_aws_key))
            else:
                key.delete()
                Logger.info('File "{}" was removed from S3'.format(dobj.cache_file_aws_key))

        os.remove(file)
        pass

    def remove_dir(self, data_dir):
        for f in os.listdir(data_dir):
            fname = os.path.join(data_dir, f)
            if os.path.isdir(fname):
                self.remove_dir(fname)
            elif os.path.islink(fname):
                self.remove_symlink(fname)
            else:
                raise DataRemoveError('Unsupported file type "{}"'.format(fname))

        os.rmdir(data_dir)
        pass


if __name__ == '__main__':
    import sys
    try:
        sys.exit(CmdDataRemove().run())
    except NeatLynxException as e:
        Logger.error(e)
        sys.exit(1)
