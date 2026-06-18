from pprint import pprint

from content_manager import *

print()
print("Images:")
pprint(discover_images())

print()
print("Video:")
print(discover_video())

print()
print("Validation:")
print(validate_content())

print()
print("Playlist:")
pprint(build_playlist())

write_playlist()
write_content_version()

print()
print("Done")
