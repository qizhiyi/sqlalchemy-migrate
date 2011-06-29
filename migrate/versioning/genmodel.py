"""
   Code to generate a Python model from a database or differences
   between a model and database.

   Some of this is borrowed heavily from the AutoCode project at:
   http://code.google.com/p/sqlautocode/
"""

import sys
import logging

import sqlalchemy

import migrate
import migrate.changeset


log = logging.getLogger(__name__)
HEADER = """
## File autogenerated by genmodel.py

from sqlalchemy import *
meta = MetaData()
"""

DECLARATIVE_HEADER = """
## File autogenerated by genmodel.py

from sqlalchemy import *
from sqlalchemy.ext import declarative

Base = declarative.declarative_base()
"""


class ModelGenerator(object):

    def __init__(self, diff, engine, declarative=False):
        self.diff = diff
        self.engine = engine
        self.declarative = declarative

    def column_repr(self, col):
        kwarg = []
        if col.key != col.name:
            kwarg.append('key')
        if col.primary_key:
            col.primary_key = True  # otherwise it dumps it as 1
            kwarg.append('primary_key')
        if not col.nullable:
            kwarg.append('nullable')
        if col.onupdate:
            kwarg.append('onupdate')
        if col.default:
            if col.primary_key:
                # I found that PostgreSQL automatically creates a
                # default value for the sequence, but let's not show
                # that.
                pass
            else:
                kwarg.append('default')
        args = ['%s=%r' % (k, getattr(col, k)) for k in kwarg]

        # crs: not sure if this is good idea, but it gets rid of extra
        # u''
        name = col.name.encode('utf8')

        type_ = col.type
        for cls in col.type.__class__.__mro__:
            if cls.__module__ == 'sqlalchemy.types' and \
                not cls.__name__.isupper():
                if cls is not type_.__class__:
                    type_ = cls()
                break

        type_repr = repr(type_)
        if type_repr.endswith('()'):
            type_repr = type_repr[:-2]

        constraints = [repr(cn) for cn in col.constraints]

        data = {
            'name': name,
            'commonStuff': ', '.join([type_repr] + args + constraints),
        }

        if self.declarative:
            return """%(name)s = Column(%(commonStuff)s)""" % data
        else:
            return """Column(%(name)r, %(commonStuff)s)""" % data

    def getTableDefn(self, table):
        out = []
        tableName = table.name
        if self.declarative:
            out.append("class %(table)s(Base):" % {'table': tableName})
            out.append("    __tablename__ = '%(table)s'\n" %
                            {'table': tableName})
            for col in table.columns:
                out.append("    %s" % self.column_repr(col))
            out.append('\n')
        else:
            out.append("%(table)s = Table('%(table)s', meta," %
                            {'table': tableName})
            for col in table.columns:
                out.append("    %s," % self.column_repr(col))
            out.append(")\n")
        return out

    def _get_tables(self,missingA=False,missingB=False,modified=False):
        to_process = []
        for bool_,names,metadata in (
            (missingA,self.diff.tables_missing_from_A,self.diff.metadataB),
            (missingB,self.diff.tables_missing_from_B,self.diff.metadataA),
            (modified,self.diff.tables_different,self.diff.metadataA),
                ):
            if bool_:
                for name in names:
                    yield metadata.tables.get(name)
        
    def toPython(self):
        """Assume database is current and model is empty."""
        out = []
        if self.declarative:
            out.append(DECLARATIVE_HEADER)
        else:
            out.append(HEADER)
        out.append("")
        for table in self._get_tables(missingA=True):
            out.extend(self.getTableDefn(table))
        return '\n'.join(out)

    def toUpgradeDowngradePython(self, indent='    '):
        ''' Assume model is most current and database is out-of-date. '''
        decls = ['from migrate.changeset import schema',
                 'meta = MetaData()']
        for table in self._get_tables(
            missingA=True,missingB=True,modified=True
            ):
            decls.extend(self.getTableDefn(table))

        upgradeCommands, downgradeCommands = [], []
        for tableName in self.diff.tables_missing_from_A:
            upgradeCommands.append("%(table)s.drop()" % {'table': tableName})
            downgradeCommands.append("%(table)s.create()" % \
                                         {'table': tableName})
        for tableName in self.diff.tables_missing_from_B:
            upgradeCommands.append("%(table)s.create()" % {'table': tableName})
            downgradeCommands.append("%(table)s.drop()" % {'table': tableName})

        for tableName in self.diff.tables_different:
            dbTable = self.diff.metadataB.tables[tableName]
            missingInDatabase, missingInModel, diffDecl = \
                self.diff.colDiffs[tableName]
            for col in missingInDatabase:
                upgradeCommands.append('%s.columns[%r].create()' % (
                        modelTable, col.name))
                downgradeCommands.append('%s.columns[%r].drop()' % (
                        modelTable, col.name))
            for col in missingInModel:
                upgradeCommands.append('%s.columns[%r].drop()' % (
                        modelTable, col.name))
                downgradeCommands.append('%s.columns[%r].create()' % (
                        modelTable, col.name))
            for modelCol, databaseCol, modelDecl, databaseDecl in diffDecl:
                upgradeCommands.append(
                    'assert False, "Can\'t alter columns: %s:%s=>%s"' % (
                    modelTable, modelCol.name, databaseCol.name))
                downgradeCommands.append(
                    'assert False, "Can\'t alter columns: %s:%s=>%s"' % (
                    modelTable, modelCol.name, databaseCol.name))
        pre_command = '    meta.bind = migrate_engine'

        return (
            '\n'.join(decls),
            '\n'.join([pre_command] + ['%s%s' % (indent, line) for line in upgradeCommands]),
            '\n'.join([pre_command] + ['%s%s' % (indent, line) for line in downgradeCommands]))

    def _db_can_handle_this_change(self,td):
        if (td.columns_missing_from_B
            and not td.columns_missing_from_A
            and not td.columns_different):
            # Even sqlite can handle this.
            return True
        else:
            return not self.engine.url.drivername.startswith('sqlite')

    def applyModel(self):
        """Apply model to current database."""

        meta = sqlalchemy.MetaData(self.engine)

        for table in self._get_tables(missingA=True):
            table = table.tometadata(meta)
            table.drop()
        for table in self._get_tables(missingB=True):
            table = table.tometadata(meta)
            table.create()
        for modelTable in self._get_tables(modified=True):
            tableName = modelTable.name
            modelTable = modelTable.tometadata(meta)
            dbTable = self.diff.metadataB.tables[tableName]

            td = self.diff.tables_different[tableName]
            
            if self._db_can_handle_this_change(td):
                
                for col in td.columns_missing_from_B:
                    modelTable.columns[col].create()
                for col in td.columns_missing_from_A:
                    dbTable.columns[col].drop()
                # XXX handle column changes here.
            else:
                # Sqlite doesn't support drop column, so you have to
                # do more: create temp table, copy data to it, drop
                # old table, create new table, copy data back.
                #
                # I wonder if this is guaranteed to be unique?
                tempName = '_temp_%s' % modelTable.name

                def getCopyStatement():
                    preparer = self.engine.dialect.preparer
                    commonCols = []
                    for modelCol in modelTable.columns:
                        if modelCol.name in dbTable.columns:
                            commonCols.append(modelCol.name)
                    commonColsStr = ', '.join(commonCols)
                    return 'INSERT INTO %s (%s) SELECT %s FROM %s' % \
                        (tableName, commonColsStr, commonColsStr, tempName)

                # Move the data in one transaction, so that we don't
                # leave the database in a nasty state.
                connection = self.engine.connect()
                trans = connection.begin()
                try:
                    connection.execute(
                        'CREATE TEMPORARY TABLE %s as SELECT * from %s' % \
                            (tempName, modelTable.name))
                    # make sure the drop takes place inside our
                    # transaction with the bind parameter
                    modelTable.drop(bind=connection)
                    modelTable.create(bind=connection)
                    connection.execute(getCopyStatement())
                    connection.execute('DROP TABLE %s' % tempName)
                    trans.commit()
                except:
                    trans.rollback()
                    raise
