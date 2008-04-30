#!/usr/bin/env python

################################################################################
#
#  qooxdoo - the new era of web development
#
#  http://qooxdoo.org
#
#  Copyright:
#    2006-2008 1&1 Internet AG, Germany, http://www.1und1.de
#
#  License:
#    LGPL: http://www.gnu.org/licenses/lgpl.html
#    EPL: http://www.eclipse.org/org/documents/epl-v10.php
#    See the LICENSE file in the project's top-level directory for details.
#
#  Authors:
#    * Sebastian Werner (wpbasti)
#
################################################################################

import re, os, sys, zlib, optparse, types, subprocess

from misc import filetool, textutil, idlist
from ecmascript import treegenerator, tokenizer, compiler
from ecmascript.optimizer import variableoptimizer
from ecmascript.optimizer import privateoptimizer
from generator.ApiLoader import ApiLoader
from generator.Cache import Cache
from generator.DependencyLoader import DependencyLoader
from generator.Locale import Locale
from generator.PartBuilder import PartBuilder
from generator.TreeLoader import TreeLoader
from generator.TreeCompiler import TreeCompiler
from generator.LibraryPath import LibraryPath
from generator.ImageInfo import ImageInfo, ImgInfoFmt
from generator.ImageClipping import ImageClipping
import simplejson
from robocopy import robocopy


memcache = {}


class Generator:
    def __init__(self, config, console, variants, settings, require, use):
        self._config = config
        self._console = console
        self._variants = variants
        self._settings = settings

        # Merge config deps and runtime deps
        require = self._mergeDicts(require, config.get("require", {}))
        use = self._mergeDicts(use, config.get("use", {}))

        # Scanning given library paths
        self.scanLibrary(config.extract("library"))

        # Create tool chain instances
        self._cache          = Cache(config.extract("cache"), self._console)
        self._treeLoader     = TreeLoader(self._classes, self._cache, self._console)
        self._depLoader      = DependencyLoader(self._classes, self._cache, self._console, self._treeLoader, require, use)
        self._treeCompiler   = TreeCompiler(self._classes, self._cache, self._console, self._treeLoader)
        self._locale         = Locale(self._classes, self._translations, self._cache, self._console, self._treeLoader)
        self._apiLoader      = ApiLoader(self._classes, self._docs, self._cache, self._console, self._treeLoader)
        self._partBuilder    = PartBuilder(self._console, self._depLoader, self._treeCompiler)
        self._imageInfo      = ImageInfo(self._console, self._cache)
        self._resourceHandler= _ResourceHandler(self)
        self._shellCmd       = _ShellCmd(self)
        self._imageClipper   = ImageClipping(self._console, self._cache)

        # Start job
        self.run()


    def _mergeDicts(self, source1, source2):
        """(non-destructive) merge source2 map into source1, but don't overwrite
           existing keys in source1 (unlike source1.update(source2)); on common
           keys, use .update() on dict values and .extend() on list values"""
        target = source1.copy()

        for key in source2:
            if not target.has_key(key):
                target[key] = source2[key]
            # dict value: update
            elif (isinstance(source2[key], types.DictType) and
                  isinstance(target[key], types.DictType)):
                target[key].update(source2[key])
            # list value: append
            elif (isinstance(source2[key], types.ListType) and
                  isinstance(target[key], types.ListType)):
                target[key].extend(source2[key])
            # leave everything else in target alone
            else:
                pass

        return target



    def scanLibrary(self, library):
        self._console.info("Scanning libraries...")
        self._console.indent()

        self._namespaces = []
        self._classes = {}
        self._docs = {}
        self._translations = {}

        for entry in library.iter():
            key = entry.get("path")
            if memcache.has_key(key):
                self._console.debug("Use memory cache for %s" % key)
                path = memcache[key]
            else:
                path = LibraryPath(entry, self._console)

            namespace = path.getNamespace()

            self._namespaces.append(namespace)
            self._classes.update(path.getClasses())
            self._docs.update(path.getDocs())
            self._translations[namespace] = path.getTranslations()

            memcache[key] = path

        self._console.outdent()
        self._console.debug("Loaded %s libraries" % len(self._namespaces))
        self._console.debug("")



    def run(self):
        # Updating translation
        self.runUpdateTranslation()

        # Preprocess include/exclude lists
        # This is only the parsing of the config values
        # We only need to call this once on each job
        smartInclude, explicitInclude = self.getIncludes(self._config.get("include", []))
        smartExclude, explicitExclude = self.getExcludes(self._config.get("exclude", []))
        
        # Processing all combinations of variants
        variantData = self.getVariants()
        variantSets = idlist.computeCombinations(variantData)

        # Iterate through variant sets
        for variantSetNum, variants in enumerate(variantSets):
            if len(variantSets) > 1:
                self._console.head("Processing variant set %s/%s" % (variantSetNum+1, len(variantSets)))

                # Debug variant combination
                self._console.debug("Switched variants:")
                self._console.indent()
                for key in variants:
                    if len(variantData[key]) > 1:
                        self._console.debug("%s = %s" % (key, variants[key]))
                self._console.outdent()


            # Resolving dependencies
            self._console.info("Resolving dependencies...")
            self._console.indent()
            classList = self._depLoader.getClassList(smartInclude, smartExclude, explicitInclude, explicitExclude, variants)
            self._classList = classList
            self._console.outdent()


            # Check for package configuration
            if self._config.get("packages"):
                # Reading configuration
                partsCfg = self._config.get("packages/parts", {})
                collapseCfg = self._config.get("packages/collapse", [])
                sizeCfg = self._config.get("packages/size", 0)
                boot = self._config.get("packages/init", "boot")

                # Automatically add boot part to collapse list
                if boot in partsCfg and not boot in collapseCfg:
                    collapseCfg.append(boot)

                # Expanding expressions
                self._console.debug("Expanding include expressions...")
                partIncludes = {}
                for partId in partsCfg:
                    partIncludes[partId] = self._expandRegExps(partsCfg[partId])

                # Computing packages
                parts, packages = self._partBuilder.getPackages(partIncludes, smartExclude, classList, collapseCfg, variants, sizeCfg)

            else:
                # Emulate configuration
                boot = "boot"
                parts = { "boot" : [0] }
                packages = [classList]



            # Execute real tasks
            self.runApiData(packages)
            self._translationMaps = self.runTranslation(parts, packages, variants)
            self.runSource(parts, packages, boot, variants)
            self.runResources()  # run before runCompiled, to get image infos
            self.runCompiled(parts, packages, boot, variants)
            self.runCopyFiles()
            self.runShellCommands()
            self.runImageSlicing()
            self.runImageCombining()
            
            
            # Debug tasks
            self.runDependencyDebug(parts, packages, variants)
            self.runPrivateDebug()            


    def runPrivateDebug(self):
        if not self._config.get("debug/privates", False):
            return

        self._console.info("Privates debugging...")
        privateoptimizer.debug()
        


    def runApiData(self, packages):
        apiPath = self._config.get("api/path")

        if not apiPath:
            return


        smartInclude, explicitInclude = self.getIncludes(self._config.get("include", []))
        smartExclude, explicitExclude = self.getExcludes(self._config.get("exclude", []))

        classList = self._depLoader.getClassList(smartInclude, smartExclude, explicitInclude, explicitExclude, {})
        packages = [classList]

        apiContent = []
        for classes in packages:
            apiContent.extend(classes)

        self._apiLoader.storeApi(apiContent, apiPath)



    def runDependencyDebug(self, parts, packages, variants):
         if not self._config.get("debug/dependencies", False):
            return

         self._console.info("Dependency debugging...")
         self._console.indent()

         for packageId, packages in enumerate(packages):
             self._console.info("Package %s" % packageId)
             self._console.indent()

             for partId in parts:
                 if packageId in parts[partId]:
                     self._console.info("Part %s" % partId)

             for classId in packages:
                 self._console.debug("Class: %s" % classId)
                 self._console.indent()

                 for otherClassId in packages:
                     otherClassDeps = self._depLoader.getDeps(otherClassId, variants)

                     if classId in otherClassDeps["load"]:
                         self._console.debug("Used by: %s (load)" % otherClassId)

                     if classId in otherClassDeps["run"]:
                         self._console.debug("Used by: %s (run)" % otherClassId)

                 self._console.outdent()
             self._console.outdent()

         self._console.outdent()



    def runUpdateTranslation(self):
        namespaces = self._config.get("translation/update")
        if not namespaces:
            return

        self._console.info("Updating translations...")
        self._console.indent()
        for namespace in namespaces:
            self._locale.updateTranslations(namespace)

        self._console.outdent()



    def runTranslation(self, parts, packages, variants):
        locales = self._config.get("localize/locales")

        if locales == None:
            return

        self._console.info("Processing translation for %s locales..." % len(locales))
        self._console.indent()

        packageTranslation = []
        for pos, classes in enumerate(packages):
            self._console.debug("Package: %s" % pos)
            self._console.indent()

            pac_dat = self._locale.generatePackageData(classes, variants, locales)
            loc_dat = self._locale.getLocalizationData(locales)
            packageTranslation.append(self._mergeDicts(pac_dat,loc_dat))

            self._console.outdent()

        self._console.outdent()
        return packageTranslation



    def runResources(self):
        generator = self

        # only run for copy jobs
        if not generator._config.get("copy-resources", False):
            return

        generator._console.info("Copying resources...")
        resTargetRoot = generator._config.get("copy-resources/target", "build")
        libs          = generator._config.get("library", [])
        generator._console.indent()
        # Copy resources
        for lib in libs:
            #libp = LibraryPath(lib,self._console)
            #ns   = libp.getNamespace()

            # construct a path to the source root for the resources
            #  (to be used later as a stripp-off from the resource source path)
            libpath = os.path.join(lib['path'],lib['resource'])
            if libpath.startswith('.'+os.sep):
                libpath = libpath[2:]

            # get relevant resources for this lib
            resList  = self._resourceHandler.findAllResources([lib], self._getDefaultResourceFilter())

            # for each needed resource
            for res in resList:
                # Get source and target paths, and invoke copying

                # Get a source path
                resSource = os.path.normpath(res[0])

                # Construct a target path
                # strip off a library prefix...
                #  relpath = respath - libprefix
                relpath = (Path.getCommonPrefix(libpath, resSource))[2]
                if relpath[0] == os.sep:
                    relpath = relpath[1:]
                # ...to construct a suitable target path
                #  target = targetRoot + relpath
                resTarget = os.path.join(resTargetRoot, 'resource', relpath)

                # Copy
                generator._copyResources(res[0], os.path.dirname(resTarget))

        generator._console.outdent()
        
        
    def runCopyFiles(self):
        # Copy application files
        if not self._config.get("copy-files/files", False):
            return

        appfiles = self._config.get("copy-files/files",[])
        if appfiles:
            buildRoot  = self._config.get("copy-files/target", "build")
            sourceRoot = self._config.get("copy-files/source", "source")
            self._console.info("Copying application files...")        
            self._console.indent()
            for file in appfiles:
                srcfile = os.path.join(sourceRoot, file)
                self._console.debug("copying %s" % srcfile)
                if (os.path.isdir(srcfile)):
                    destfile = os.path.join(buildRoot,file)
                else:
                    destfile = os.path.join(buildRoot, os.path.dirname(file))
                self._copyResources(srcfile, destfile)

            self._console.outdent()
        
        
    def runShellCommands(self):
        if not self._config.get("shell/command", False):
            return

        shellcmd = self._config.get("shell/command", "")
        if shellcmd:
            rc = 0
            self._console.info("Executing shell command \"%s\"..." % shellcmd)
            self._console.indent()
            rc = self._shellCmd.execute(shellcmd)
            self._console.debug("exist status from shell command: %s" % repr(rc))

            self._console.outdent()


    def runCompiled(self, parts, packages, boot, variants):
        if not self._config.get("compile/file"):
            return

        # Read in base file name
        filePath = self._config.get("compile/file")

        # Read in relative file name
        fileUri = self._config.get("compile/uri", filePath)

        # Read in compiler options
        optimize = self._config.get("compile/optimize", [])

        # Whether the code should be formatted
        format = self._config.get("compile/format", False)

        # Read in settings
        settings = self.getSettings()

        # Get resource list
        buildUri = self._config.get('compile/resourceUri', ".")
        libs = [{
                 'path':'.', 
                 'namespace':'build',
                 'class' : 'build',
                 'resource': 'build/resource',
                 'translation': 'build/translation',
                 'uri': buildUri, 
                 'encoding':'utf-8'
            }]  # use what's in the 'build' tree -- this depends on resource copying!!
        #resourceList = self._resourceHandler.findAllResources(libs, self._getDefaultResourceFilter())

        # Generating boot script
        self._console.info("Generating boot script...")

        bootBlocks = []
        bootBlocks.append(self.generateSettingsCode(settings, format))
        bootBlocks.append(self.generateVariantsCode(variants, format))
        bootBlocks.append(self.generateResourceUriCode(libs, format))
        bootBlocks.append(self.generateImageInfoCode(settings, libs, format))
        bootBlocks.append(self.generateTranslationCode(self._translationMaps, format))
        bootBlocks.append(self.generateCompiledPackageCode(fileUri, parts, packages, boot, variants, settings, format))

        if format:
            bootContent = "\n\n".join(bootBlocks)
        else:
            #bootContent = self._optimizeJavaScript("".join(bootBlocks))
            bootContent = "".join(bootBlocks)

        # Resolve file name variables
        resolvedFilePath = self._resolveFileName(filePath, variants, settings)

        # Save result file
        filetool.save(resolvedFilePath, bootContent)

        if self._config.get("compile/gzip"):
            filetool.gzip(resolvedFilePath, bootContent)

        self._console.debug("Done: %s" % self._computeContentSize(bootContent))
        self._console.debug("")


        # Generating packages
        self._console.info("Generating packages...")
        self._console.indent()

        for packageId, packages in enumerate(packages):
            self._console.info("Compiling package #%s:" % packageId, False)
            self._console.indent()

            # Compile file content
            compiledContent = self._treeCompiler.compileClasses(packages, variants, optimize, format)

            # Construct file name
            resolvedFilePath = self._resolveFileName(filePath, variants, settings, packageId)

            # Save result file
            filetool.save(resolvedFilePath, compiledContent)

            if self._config.get("compile/gzip"):
                filetool.gzip(resolvedFilePath, compiledContent)

            self._console.debug("Done: %s" % self._computeContentSize(compiledContent))
            self._console.outdent()

        self._console.outdent()
        

    def runSource(self, parts, packages, boot, variants):
        if not self._config.get("script/file"):
            return

        self._console.info("Generate source version...")
        self._console.indent()

        # Read in base file name
        filePath = self._config.get("script/file")

        # Whether the code should be formatted
        format = self._config.get("source/format", False)

        # Read in settings
        settings = self.getSettings()

        # Get resource list
        libs = self._config.get("library", [])
        #resourceList = self._resourceHandler.findAllResources(libs, self._getDefaultResourceFilter())
        
        # Add data from settings, variants and packages
        sourceBlocks = []
        sourceBlocks.append(self.generateSettingsCode(settings, format))
        sourceBlocks.append(self.generateVariantsCode(variants, format))
        sourceBlocks.append(self.generateResourceUriCode(self._config.get("library",[]),format))        
        sourceBlocks.append(self.generateImageInfoCode(settings, libs, format))
        sourceBlocks.append(self.generateTranslationCode(self._translationMaps, format))
        sourceBlocks.append(self.generateSourcePackageCode(parts, packages, boot, format))

        # TODO: Do we really need this optimization here. Could this be solved
        # with less resources just through directly generating "good" code?
        self._console.info("Generating boot loader...")
        if format:
            sourceContent = "\n\n".join(sourceBlocks)
        else:
            #sourceContent = self._optimizeJavaScript("".join(sourceBlocks))
            sourceContent = "".join(sourceBlocks)
        self._console.info("Done")

        # Construct file name
        resolvedFilePath = self._resolveFileName(filePath, variants, settings)

        # Save result file
        filetool.save(resolvedFilePath, sourceContent)

        if self._config.get("source/gzip"):
            filetool.gzip(resolvedFilePath, sourceContent)

        self._console.outdent()
        self._console.debug("Done: %s" % self._computeContentSize(sourceContent))
        self._console.outdent()


    def runImageSlicing(self):
        """Go through a list of images and slice each one into subimages"""
        if not self._config.get("slice-images", False):
            return

        images = self._config.get("slice-images/images", {})
        for image, imgspec in images.iteritems():
            prefix       = imgspec['prefix']
            border_width = imgspec['border-width']
            self._imageClipper.slice(image, prefix, border_width)
        
    
    def runImageCombining(self):
        """Go through a list of images and create them as combination of other images"""
        if not self._config.get("combine-images", False):
            return

        images = self._config.get("combine-images/images", {})
        for image, imgspec in images.iteritems():
            config = {}
            input  = imgspec['input']
            layout = imgspec['layout'] == "horizontal"
            # create the combined image
            subconfigs = self._imageClipper.combine(image, input, layout)
            for sub in subconfigs:
                x = ImgInfoFmt()
                x.mappeduri, x.left, x.top, x.width, x.height, x.type = (
                   sub['combined'], sub['left'], sub['top'], sub['width'], sub['height'], sub['type'])
                config[sub['file']] = x.flatten()
            # store meta data for this combined image
            bname = os.path.basename(image)
            ri = bname.rfind('.')
            if ri > -1:
                bname = bname[:ri]
            bname += '.meta'
            meta_fname = os.path.join(os.path.dirname(image), bname)
            filetool.save(meta_fname, simplejson.dumps(config, ensure_ascii=False))
            # cache meta data
        return



    ######################################################################
    #  SETTINGS/VARIANTS/PACKAGE DATA
    ######################################################################

    def getSettings(self):
        settings = {}
        settingsConfig = self._config.get("settings", {})
        settingsRuntime = self._settings

        for key in settingsConfig:
            settings[key] = settingsConfig[key]

        for key in settingsRuntime:
            settings[key] = settingsRuntime[key]

        return settings


    def getVariants(self):
        variants = {}
        variantsConfig = self._config.get("variants", {})
        variantsRuntime = self._variants

        for key in variantsConfig:
            variants[key] = variantsConfig[key]

        for key in variantsRuntime:
            variants[key] = [variantsRuntime[key]]

        return variants


    def _toJavaScript(self, value):
        number = re.compile("^([0-9\-]+)$")

        if not (value == "false" or value == "true" or value == "null" or number.match(value)):
            value = '"%s"' % value.replace("\"", "\\\"")

        return value


    def generateSettingsCode(self, settings, format=False):
        result = 'if(!window.qxsettings)qxsettings={};'

        for key in settings:
            if format:
                result += "\n"

            value = self._toJavaScript(settings[key])
            result += 'qxsettings["%s"]=%s;' % (key, value)

        return result


    def generateVariantsCode(self, variants, format=False):
        result = 'if(!window.qxvariants)qxvariants={};'

        for key in variants:
            if format:
                result += "\n"

            value = self._toJavaScript(variants[key])
            result += 'qxvariants["%s"]=%s;' % (key, value)

        return result


    def generateResourceUriCode(self, libs, format):
        result = 'if(!window.qxresourceuris)qxresourceuris={};'

        for lib in libs:
            result += 'qxresourceuris["%s"]="%s";' % (lib['namespace'], 
                                                  os.path.join(lib['uri'],lib['resource']))
        return result


    def generateImageInfoCode(self, settings, libs, format=False):
        """Pre-calculate image information (e.g. sizes)"""
        data = {}
        imgpatt = re.compile(r'\.(png|jpeg|gif)$', re.I)

        self._console.info("Analysing images...")
        self._console.indent()

        def replaceWithNamespace(imguri, liburi, libns):
            pre,libsfx,imgsfx = Path.getCommonPrefix(liburi, imguri)
            if imgsfx[0] == os.sep: imgsfx = imgsfx[1:]  # strip leading '/'
            imgshorturi = os.path.join("${%s}" % libns, imgsfx)
            return imgshorturi

        def normalizeImgUri(uriFromMetafile, trueCombinedUri, combinedUriFromMetafile):
            # get the "wrong" prefix (in mappedUriPrefix)
            trueUriPrefix, mappedUriPrefix, sfx = Path.getCommonSuffix(trueCombinedUri, combinedUriFromMetafile)
            # ...and strip it from contained image uri, to get a correct suffix (in uriSuffix)
            pre, mappedUriSuffix, uriSuffix = Path.getCommonPrefix(mappedUriPrefix, uriFromMetafile)
            # ...then compose the correct prefix with the correct suffix
            normalUri = trueUriPrefix + uriSuffix
            return normalUri
        
        for lib in libs:
            libresuri = os.path.join(lib['uri'],lib['resource'])
            resourceList = self._resourceHandler.findAllResources([lib], self._getDefaultResourceFilter())
            # resourceList = [[file1,uri1],[file2,uri2],...]
            for resource in (x for x in resourceList if imgpatt.search(x[0])):
                # resource = [path, uri]
                imgpath= resource[0]
                imguri = resource[1]
                imageInfo = self._imageInfo.getImageInfo(imgpath)

                # imageInfo = {width, height, filetype}
                if not 'width' in imageInfo or not 'height' in imageInfo or not 'type' in imageInfo:
                    self._console.error("Unable to get image info from file: %s" % resource[0])
                    sys.exit(1)
                # use an ImgInfoFmt object, to abstract from flat format
                imgfmt = ImgInfoFmt()
                imgfmt.width, imgfmt.height, imgfmt.type = (
                    imageInfo['width'], imageInfo['height'], imageInfo['type'])
                # replace lib uri with lib namespace in imguri
                imgshorturi = replaceWithNamespace(imguri, libresuri, lib['namespace'])
                # check if img is already registered as part of a combined image
                if imgshorturi in data:
                    x = ImgInfoFmt(data[imgshorturi])
                    if x.mappeduri:
                        continue  # don't overwrite the combined entry
                data[imgshorturi] = imgfmt.flatten()

                # check for a combined image and process the contained images
                meta_fname = os.path.splitext(imgpath)[0]+'.meta'
                if os.path.exists(meta_fname):  # add included imgs
                    cimguri      = imguri       # we realize this is a combined imgage
                    cimgshorturi = imgshorturi
                    # read meta file
                    mfile = open(meta_fname)
                    imgDict = simplejson.loads(mfile.read())
                    mfile.close()
                    for mimg, mimgs in imgDict.iteritems():
                        # sort of like this: mimg : [width, height, type, combinedUri, off-x, off-y]
                        mimgspec = ImgInfoFmt(mimgs)
                        # have to normalize the uri's from the meta file
                        # cimguri is relevant, like: "../../framework/source/resource/qx/decoration/Modern/panel-combined.png"
                        # mimg is an uri from when the meta file was generated, like: "./source/resource/qx/decoration/Modern/..."
                        mimguri = normalizeImgUri(mimg, cimguri, mimgspec.mappeduri)
                        # replace lib uri with lib namespace in mimguri
                        mimgshorturi = replaceWithNamespace(mimguri, libresuri, lib['namespace'])

                        mimgspec.mappeduri = cimgshorturi        # correct the mapped uri of the combined image
                        data[mimgshorturi] = mimgspec.flatten()  # this information takes precedence over existing
                
        result = 'if(!window.qximageinfo)qximageinfo=' + simplejson.dumps(data,ensure_ascii=False) + ";"
            
        self._console.outdent()

        return result


    def generateTranslationCode(self, translationMaps, format=False):
        if translationMaps == None:
            return ""

        self._console.info("Generate translation code...")

        result = 'if(!window.qxlocales)qxlocales={};'
        locales = translationMaps[0]  # TODO: just one currently

        for key in locales:
            if format:
                result += "\n"

            value = locales[key]
            result += 'qxlocales["%s"]=' % (key,)
            result += simplejson.dumps(value)
            result += ';'

        return result


    def generateSourcePackageCode(self, parts, packages, boot, format=False):
        if not parts:
            return ""

        # Translate part information to JavaScript
        partData = "{"
        for partId in parts:
            partData += '"%s":' % (partId)
            partData += ('%s,' % parts[partId]).replace(" ", "")

        partData=partData[:-1] + "}"

        # Translate URI data to JavaScript
        allUris = []
        for packageId, packages in enumerate(packages):
            packageUris = []
            for fileId in packages:
                packageUris.append('"%s"' % self._classes[fileId]["uri"])

            allUris.append("[" + ",".join(packageUris) + "]")

        uriData = "[" + ",\n".join(allUris) + "]"

        # Locate and load loader basic script
        loaderFile = os.path.join(filetool.root(), "data", "generator", "loader.js")
        result = filetool.read(loaderFile)

        # Replace template with computed data
        result = result.replace("%PARTS%", partData)
        result = result.replace("%URIS%", uriData)
        result = result.replace("%BOOT%", '"%s"' % boot)

        return result


    def generateCompiledPackageCode(self, fileName, parts, packages, boot, variants, settings, format=False):
        if not parts:
            return ""

        # Translate part information to JavaScript
        partData = "{"
        for partId in parts:
            partData += '"%s":' % (partId)
            partData += ('%s,' % parts[partId]).replace(" ", "")

        partData=partData[:-1] + "}"

        # Translate URI data to JavaScript
        allUris = []
        for packageId, packages in enumerate(packages):
            packageFileName = self._resolveFileName(fileName, variants, settings, packageId)
            allUris.append('["' + packageFileName + '"]')

        uriData = "[" + ",\n".join(allUris) + "]"

        # Locate and load loader basic script
        loaderFile = os.path.join(filetool.root(), "data", "generator", "loader.js")
        result = filetool.read(loaderFile)

        # Replace template with computed data
        result = result.replace("%PARTS%", partData)
        result = result.replace("%URIS%", uriData)
        result = result.replace("%BOOT%", '"%s"' % boot)

        return result







    ######################################################################
    #  DEPENDENCIES
    ######################################################################

    def getIncludes(self, includeCfg):
        #includeCfg = self._config.get("include", [])

        # Splitting lists
        self._console.debug("Preparing include configuration...")
        smartInclude, explicitInclude = self._splitIncludeExcludeList(includeCfg)
        self._console.indent()

        if len(smartInclude) > 0 or len(explicitInclude) > 0:
            # Configuration feedback
            self._console.debug("Including %s items smart, %s items explicit" % (len(smartInclude), len(explicitInclude)))

            if len(explicitInclude) > 0:
                self._console.warn("Explicit included classes may not work")

            # Resolve regexps
            self._console.debug("Expanding expressions...")
            smartInclude = self._expandRegExps(smartInclude)
            explicitInclude = self._expandRegExps(explicitInclude)

        elif self._config.get("packages"):
            # Special part include handling
            self._console.info("Including part classes...")
            partsCfg = partsCfg = self._config.get("packages/parts", {})
            smartInclude = []
            for partId in partsCfg:
                smartInclude.extend(partsCfg[partId])

            # Configuration feedback
            self._console.debug("Including %s items smart, %s items explicit" % (len(smartInclude), len(explicitInclude)))

            # Resolve regexps
            self._console.debug("Expanding expressions...")
            smartInclude = self._expandRegExps(smartInclude)

        self._console.outdent()

        return smartInclude, explicitInclude



    def getExcludes(self, excludeCfg):
        #excludeCfg = self._config.get("exclude", [])

        # Splitting lists
        self._console.debug("Preparing exclude configuration...")
        smartExclude, explicitExclude = self._splitIncludeExcludeList(excludeCfg)

        # Configuration feedback
        self._console.indent()
        self._console.debug("Excluding %s items smart, %s items explicit" % (len(smartExclude), len(explicitExclude)))

        if len(excludeCfg) > 0:
            self._console.warn("Excludes may break code!")

        self._console.outdent()

        # Resolve regexps
        self._console.indent()
        self._console.debug("Expanding expressions...")
        smartExclude = self._expandRegExps(smartExclude)
        explicitExclude = self._expandRegExps(explicitExclude)
        self._console.outdent()

        return smartExclude, explicitExclude



    def _splitIncludeExcludeList(self, data):
        intelli = []
        explicit = []

        for entry in data:
            if entry[0] == "=":
                explicit.append(entry[1:])
            else:
                intelli.append(entry)

        return intelli, explicit



    def _expandRegExps(self, entries):
        result = []

        for entry in entries:
            # Fast path: Try if a matching class could directly be found
            if entry in self._classes:
                result.append(entry)

            else:
                regexp = textutil.toRegExp(entry)
                expanded = []

                for classId in self._classes:
                    if regexp.search(classId):
                        if not classId in expanded:
                            expanded.append(classId)

                if len(expanded) == 0:
                    self._console.error("Expression gives no results. Malformed entry: %s" % entry)
                    sys.exit(1)

                result.extend(expanded)

        return result



    def _resolveFileName(self, fileName, variants=None, settings=None, packageId=""):
        if variants:
            for key in variants:
                pattern = "{%s}" % key
                fileName = fileName.replace(pattern, variants[key])

        if settings:
            for key in settings:
                pattern = "{%s}" % key
                fileName = fileName.replace(pattern, settings[key])

        if packageId != "":
            fileName = fileName.replace(".js", "-%s.js" % packageId)

        return fileName


    def _computeContentSize(self, content):
        # Convert to utf-8 first
        uni = unicode(content).encode("utf-8")

        # Calculate sizes
        origSize = len(uni) / 1024
        compressedSize = len(zlib.compress(uni, 9)) / 1024

        return "%sKB / %sKB" % (origSize, compressedSize)


    def _optimizeJavaScript(self, code):
        restree = treegenerator.createSyntaxTree(tokenizer.parseStream(code))
        variableoptimizer.search(restree)

        # Emulate options
        parser = optparse.OptionParser()
        parser.add_option("--p1", action="store_true", dest="prettyPrint", default=False)
        parser.add_option("--p2", action="store_true", dest="prettypIndentString", default="  ")
        parser.add_option("--p3", action="store_true", dest="prettypCommentsInlinePadding", default="  ")
        parser.add_option("--p4", action="store_true", dest="prettypCommentsTrailingCommentCols", default="")

        (options, args) = parser.parse_args([])

        return compiler.compile(restree, options)



    def _copyResources(self, srcPath, targPath):
        # targPath *has* to be directory  -- there is now way of telling a
        # non-existing target file from a non-existing target directory :-)
        generator = self
        generator._console.debug("_copyResource: %s => %s" % (srcPath, targPath))
        copier = robocopy.PyRobocopier(generator._console)
        copier.parse_args(['-c', '-s', '-x', '.svn', srcPath, targPath])
        copier.do_work()


    def _getDefaultResourceFilter(self, useAssets=True):
        '''Just a utility function to easily switch between resource filters in
           all invocations to findAllResources(); also shows how a filter argument
           might look like'''
        #return None
        if useAssets: # this was the old 'resource-filter : true' config setting
            # select a resource whether it is used by a class
            return self._resourceHandler.filterResourcesByClasslist(self._classList)
        else:
            #return self._resourceHandler.filterResourcesByFilepath(re.compile(r'.*/qx/icon/.*'), lambda x: not x) # only res paths that do *not* match '/qx/icon/'
            return self._resourceHandler.filterResourcesByFilepath() 



class _ResourceHandler(object):
    def __init__(self, generatorobj):
        self._genobj  = generatorobj
        self._resList = None


    def findAllResources(self, libraries, filter=None):
        """Find relevant resources/assets, implementing shaddowing of resources.
           Returns a list of resources, each a pair of [file_path, uri]"""
        result = []
        
        # go through all libs (weighted) and collect necessary resources
        # fallback: take all resources
        libs = libraries[:]
        libs.reverse()

        for lib in libs:
            #ns = lib['path']
            ns = lib['namespace']
            # path to the lib resource root
            libpath = os.path.join(lib['path'],lib['resource'])
            libpath = os.path.normpath(libpath)  # normalize "./..."
            # check and populate cache of files on disk (reduce disk I/O)
            cacheId = "resinlib-%s" % ns
            liblist = self._genobj._cache.read(cacheId, dependsOn=None, memory=True)
            if liblist == None:
                liblist = filetool.find(libpath)  # liblist is a generator, therefore we
                llist   = []                      # cannot write it out just now
                inCache = False
            else:
                inCache = True

            # for each resource path in library
            for rsrc in liblist:
                if not inCache:
                    llist.append(rsrc)
                # is this file considered necessary?
                if (filter and not filter(rsrc)):
                    continue
                else:
                    # create a pair res = [path, uri] for this resource...
                    res = []
                    rsource = os.path.normpath(rsrc)  # normalize "./..."
                    relpath = (Path.getCommonPrefix(libpath, rsource))[2]
                    if relpath[0] == os.sep:  # normalize "/..."
                        relpath = relpath[1:]
                    res.append(rsource)
                    res.append(os.path.join(lib['uri'],lib['resource'],relpath))
                    # ...and add it to the result list
                    result.append(res)

            if not inCache:
                    self._genobj._cache.write(cacheId, llist, memory=True, writeToFile=False)

        return result


    def filterResourcesByClasslist(self, classes):
        # returns a function that takes a resource path and return true if one
        # of the <classes> needs it

        if not self._resList:
            self._resList = self._getResourcelistFromClasslist(classes)  # get consolidated resource list
        respatt = re.compile(r'[^/]+?/')  # everything before the first slash
        def filter(respath):
            for res in self._resList:
                #res1 = respatt.sub('',res,1)  # strip off e.g 'qx.icontheme/'...
                res1 = res
                if re.search(res1, respath):  # this might need a better 'match' algorithm
                    return True
            return False
        
        return filter
    
    
    def filterResourcesByFilepath(self, filepatt=None, inversep=lambda x: x):
        """Returns a filter function that takes a resource path and returns
           True/False, depending on whether the resource should be included.
           <filepatt> pattern to match against a resource path, <inversep> if
           the match result should be reversed (for exclusions)"""
        if not filepatt:
            #filepatt = re.compile(r'\.(?:png|jpeg|gif)$', re.I)
            filepatt = re.compile(r'.*/resource/.*')
        
        def filter(respath):
            if inversep(re.search(filepatt,respath)):
                return True
            else:
                return False
        
        return filter
    

    def _getResourcelistFromClasslist(self, classList):
        """Return a consolidated list of resource fileId's of all classes in classList; 
           handles meta info."""
        result = []

        self._genobj._console.info("Compiling resource list...")
        self._genobj._console.indent()
        for clazz in classList:
            classRes = (self._genobj._depLoader.getMeta(clazz))['assetDeps'][:]
            iresult  = []
            for res in classRes:
                # here it might need some massaging of 'res' before lookup and append
                # expand file glob into regexp
                res = re.sub(r'\*', ".*", res)
                # expand macros
                if res.find('${')>-1:
                    expres = self._expandMacrosInMeta(res)
                else:
                    expres = [res]
                for r in expres:
                    if r not in result + iresult:
                        iresult.append(r)
            self._genobj._console.debug("%s: %s" % (clazz, repr(iresult)))
            result.extend(iresult)

        self._genobj._console.outdent()
        return result


    def _expandMacrosInMeta(self, res):
        themeinfo = self._genobj._config.get('themes',{})

        def expMacRec(rsc):
            if rsc.find('${')==-1:
                return [rsc]
            result = []
            nres = rsc[:]
            mo = re.search(r'\$\{(.*?)\}',rsc)
            if mo:
                themekey = mo.group(1)
                if themekey in themeinfo:
                    # create an array with all possibly variants for this replacement
                    iresult = []
                    for val in themeinfo[themekey]:
                        iresult.append(nres.replace('${'+themekey+'}', val))
                    # for each variant replace the remaining macros
                    for ientry in iresult:
                        result.extend(expMacRec(ientry))
                else:
                    nres = nres.replace('${'+themekey+'}','') # just remove '${...}'
                    result.append(os.path.normpath(nres))     # get rid of '...//...'
                    self._genobj._console.warn("Empty replacement of macro '%s' in asset spec." % themekey)
            else:
                raise SyntaxError, "Non-terminated macro in string: %s" % rsc
            return result

        result = expMacRec(res)
        return result


class _ShellCmd(object):
    def __init__(self, generatorobj):
        self._genobj = generatorobj

    
    def eval_wait(self, rcode):
        lb = (rcode << 8) >> 8 # get low-byte from 16-bit word
        if (lb == 0):  # check low-byte for signal
            rc = rcode >> 8  # high-byte has exit code
        else:
            rc = lb  # return signal/coredump val
        return rc


    def execute(self,cmd):
        # subprocess-based version
        p = subprocess.Popen(cmd, shell=True,
                             # problems in python 2.4.4 with passing std streams (?)
                             #stdout=sys.stdout,
                             #stderr=subprocess.STDOUT
                             #stderr=sys.stderr
                             )
        return p.wait()


    def execute_piped(cmd):
        p = subprocess.Popen(cmd, shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             universal_newlines=True)
        output, errout = p.communicate()
        rcode = p.returncode

        return (rcode, output, errout)


    def execute1(self, shellcmd):
        # os-based version; bombs intermittendly due to os.wait() coming too late
        (cin,couterr) = os.popen4(shellcmd)
        cin.close()  # no need to pass data to child
        couterrNo = couterr.fileno()
        stdoutNo  = sys.stdout.fileno()
        while(1):
            buf = os.read(couterrNo,50)
            if buf == "":
                break
            os.write(stdoutNo,buf)
        (pid,rcode) = os.wait()  # wish: (os.wait())[1] >> 8 -- unreliable on Windows
        rc = self.eval_wait(rcode)

        return rc


class Path (object):
    '''provide extra path functions beyond os.path'''
    def _getCommonSuffix(p1, p2):
        '''computes the common suffix of path1, path2, and returns the two different prefixes
           and the common suffix'''
        pre1 = pre2 = suffx = ""
        for i in range(1,len(p1)):
            if i > len(p2):
                break
            elif p1[-i] == p2[-i]:
                suffx = p1[-i] + suffx
            else:
                break
        pre1 = p1[:-i+1]
        pre2 = p2[:-i+1]

        return pre1, pre2, suffx

    getCommonSuffix = staticmethod(_getCommonSuffix)


    def _getCommonPrefix(p1, p2):
        '''computes the common prefix of p1, p2, and returns the common prefix and the two
           different suffixes'''
        pre = sfx1 = sfx2 = ""
        for i in range(len(p1)):
            if i > len(p2):
                break
            elif p1[i] == p2[i]:
                pre += p1[i]
            else:
                i -= 1  # correct i, since the loop ends differently with range() or !=
                break
        sfx1 = p1[i+1:]
        sfx2 = p2[i+1:]

        return pre,sfx1,sfx2

    getCommonPrefix = staticmethod(_getCommonPrefix)

